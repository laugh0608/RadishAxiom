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
fn limits() -> EffectLimits {
    EffectLimits {
        ir_json: json_limits(),
        max_steps: 200_000,
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
fn target(set: &ObligationSet) -> &str {
    set.obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::EffectEmpty)
        .unwrap()
        .id()
}
fn derive(document: &CanonicalDocument, set: &ObligationSet) -> EffectDerivation {
    derive_empty_effects(
        EffectProfile::CoreV0_1,
        document,
        set,
        target(set),
        &identity(),
        limits(),
    )
    .unwrap()
}
fn baseline() -> CanonicalDocument {
    load("contracts/map-filter-query-v0.1/inputs/identity.jcs")
}

#[test]
fn full_records_match_independent_rules_and_both_paths_reject_mutations() {
    let directory = std::env::temp_dir().join(format!("radishaxiom-p3e-{}", std::process::id()));
    std::fs::create_dir(&directory).unwrap();
    let mut total = 0;
    for line in include_str!("../../../../contracts/core-empty-effects-v0.1/cases.tsv").lines() {
        let c: Vec<_> = line.split('\t').collect();
        let document = load(c[1]);
        assert_eq!(raw_digest(document.canonical_bytes()), c[2]);
        let obligations = set(&document);
        let record = derive(&document, &obligations);
        assert_eq!(
            record.canonical_bytes(),
            std::fs::read(root().join(c[3])).unwrap(),
            "{}",
            c[0]
        );
        assert_eq!(record.artifact_digest(), c[4]);
        let u = record.usage();
        assert_eq!(
            [u.steps, u.premise_edges, u.path_bytes, u.output_bytes],
            c[5..]
                .iter()
                .map(|v| v.parse().unwrap())
                .collect::<Vec<usize>>()
                .as_slice()
        );
        assert_eq!(
            check_empty_effects(
                EffectProfile::CoreV0_1,
                record.canonical_bytes(),
                &document,
                &obligations,
                target(&obligations),
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
    assert_eq!(total, 88);
    let result = std::process::Command::new("python3")
        .arg(root().join("scripts/check-p3-effect-derivations.py"))
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
    let mut mutants = 0;
    for line in std::fs::read_to_string(directory.join("mutations.tsv"))
        .unwrap()
        .lines()
    {
        let (source, path) = line.split_once('\t').unwrap();
        let document = load(source);
        let obligations = set(&document);
        let bytes = std::fs::read(directory.join(path)).unwrap();
        assert!(matches!(
            check_empty_effects(
                EffectProfile::CoreV0_1,
                &bytes,
                &document,
                &obligations,
                target(&obligations),
                &identity(),
                limits()
            ),
            Err(EffectError::NonCanonical { .. })
        ));
        mutants += 1;
    }
    assert_eq!(mutants, 28);
    let mut negatives = 0;
    for line in std::fs::read_to_string(directory.join("negatives.tsv"))
        .unwrap()
        .lines()
    {
        let (source, path) = line.split_once('\t').unwrap();
        let document = load(source);
        let bytes = std::fs::read(directory.join(path)).unwrap();
        assert!(normalize_document(&bytes, json_limits()).is_err());
        // 独立脚本的坏树只用于局部规则拒绝；不伪称可由公开 P1 构造。
        let value = json::parse(&bytes, json_limits()).unwrap();
        let mut builder = rules::Builder::new(limits());
        assert!(
            matches!(
                builder.document(&value, &document),
                Err(EffectError::InvalidConstruct { .. })
            ),
            "{path}"
        );
        negatives += 1;
    }
    assert_eq!(negatives, 7);
    std::fs::remove_dir_all(directory).unwrap();
}

#[test]
fn exact_budgets_and_overflow_fail_without_partial_records() {
    let document = baseline();
    let obligations = set(&document);
    let record = derive(&document, &obligations);
    let u = record.usage();
    let exact = EffectLimits {
        ir_json: json_limits(),
        max_steps: u.steps,
        max_premise_edges: u.premise_edges,
        max_path_bytes: u.path_bytes,
        max_output_bytes: u.output_bytes,
    };
    assert_eq!(
        derive_empty_effects(
            EffectProfile::CoreV0_1,
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            exact
        )
        .unwrap(),
        record
    );
    for resource in [
        EffectResource::Steps,
        EffectResource::PremiseEdges,
        EffectResource::PathBytes,
        EffectResource::OutputBytes,
    ] {
        for zero in [false, true] {
            let mut small = exact;
            let limit = match resource {
                EffectResource::Steps => &mut small.max_steps,
                EffectResource::PremiseEdges => &mut small.max_premise_edges,
                EffectResource::PathBytes => &mut small.max_path_bytes,
                EffectResource::OutputBytes => &mut small.max_output_bytes,
            };
            *limit = if zero { 0 } else { *limit - 1 };
            assert!(
                matches!(derive_empty_effects(EffectProfile::CoreV0_1, &document, &obligations, target(&obligations), &identity(), small), Err(EffectError::ResourceLimit { resource: actual }) if actual == resource)
            );
        }
        let mut budget = Budget {
            limits: EffectLimits {
                max_steps: usize::MAX,
                max_premise_edges: usize::MAX,
                max_path_bytes: usize::MAX,
                max_output_bytes: usize::MAX,
                ..limits()
            },
            usage: EffectUsage::default(),
        };
        budget.charge(resource, Some(usize::MAX)).unwrap();
        assert_eq!(
            budget.charge(resource, Some(1)),
            Err(EffectError::ResourceLimit { resource })
        );
        assert_eq!(
            budget.charge(resource, None),
            Err(EffectError::ResourceLimit { resource })
        );
    }
    let mut small = exact;
    small.ir_json.max_input_bytes = document.canonical_bytes().len() - 1;
    assert!(matches!(
        derive_empty_effects(
            EffectProfile::CoreV0_1,
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            small
        ),
        Err(EffectError::Json(_))
    ));
    small = exact;
    small.ir_json.max_values = 1;
    assert!(matches!(
        derive_empty_effects(
            EffectProfile::CoreV0_1,
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            small
        ),
        Err(EffectError::Json(_))
    ));
    small = exact;
    small.max_output_bytes -= 1;
    assert!(matches!(
        check_empty_effects(
            EffectProfile::CoreV0_1,
            record.canonical_bytes(),
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            small
        ),
        Err(EffectError::ResourceLimit {
            resource: EffectResource::OutputBytes
        })
    ));
}

#[test]
fn identities_profile_isolation_and_original_order_are_explicit() {
    let document = baseline();
    let obligations = set(&document);
    let record = derive(&document, &obligations);
    let other = load("contracts/map-filter-query-v0.1/inputs/filter-capacity.jcs");
    assert!(matches!(
        derive_empty_effects(
            EffectProfile::CoreV0_1,
            &other,
            &obligations,
            target(&obligations),
            &identity(),
            limits()
        ),
        Err(EffectError::BindingMismatch)
    ));
    assert!(matches!(
        derive_empty_effects(
            EffectProfile::CoreV0_1,
            &document,
            &obligations,
            "missing",
            &identity(),
            limits()
        ),
        Err(EffectError::UnknownObligation(_))
    ));
    for item in obligations
        .obligations()
        .iter()
        .filter(|o| o.kind() != ObligationKind::EffectEmpty)
    {
        assert!(
            matches!(derive_empty_effects(EffectProfile::CoreV0_1, &document, &obligations, item.id(), &identity(), limits()), Err(EffectError::UnsupportedKind(kind)) if kind == item.kind())
        );
    }
    let changed = GeneratorIdentity::new(&format!("sha256:{}", "b".repeat(64))).unwrap();
    assert!(matches!(
        check_empty_effects(
            EffectProfile::CoreV0_1,
            record.canonical_bytes(),
            &document,
            &obligations,
            target(&obligations),
            &changed,
            limits()
        ),
        Err(EffectError::NonCanonical { .. })
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
        check_empty_effects(
            EffectProfile::CoreV0_1,
            &bytes,
            &document,
            &obligations,
            target(&obligations),
            &identity(),
            limits()
        ),
        Err(EffectError::NonCanonical { .. })
    ));
    let old = load("crates/axiom-ir/tests/fixtures/document-identities/contract.jcs");
    assert!(matches!(
        derive_empty_effects(
            EffectProfile::CoreV0_1,
            &old,
            &obligations,
            target(&obligations),
            &identity(),
            limits()
        ),
        Err(EffectError::UnsupportedIrVersion(IrVersion::V0_1))
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
                ObligationKind::EffectEmpty
            ))
        ));
    }
}

#[test]
fn deep_shared_graph_and_huge_capacity_do_not_expand_worlds() {
    let document = load("contracts/map-filter-query-v0.1/resource-inputs/deep-type-and-graph.jcs");
    let obligations = set(&document);
    let record = derive(&document, &obligations);
    assert_eq!(record.usage().steps, 10006); // input + 5000 × (predicate, filter) + output + formula / contract + effects / program
    let value = json::parse(record.canonical_bytes(), json_limits()).unwrap();
    let Value::Object(root) = value else {
        unreachable!()
    };
    let Value::Array(steps) = &root.iter().find(|(k, _, _)| k == "steps").unwrap().1 else {
        unreachable!()
    };
    assert_eq!(steps.len(), record.usage().steps);
    for path in [
        "contracts/map-filter-query-v0.2/resource-inputs/huge-input.jcs",
        "contracts/map-filter-query-v0.1/resource-inputs/nested-expansion.jcs",
    ] {
        let document = load(path);
        let obligations = set(&document);
        assert!(derive(&document, &obligations).usage().steps < 1000);
    }
}

#[test]
fn forbidden_capabilities_are_rejected_before_derivation() {
    let document = baseline();
    let mut value = json::parse(document.canonical_bytes(), json_limits()).unwrap();
    let Value::Object(root) = &mut value else {
        unreachable!()
    };
    *declarations::member_mut(root, "effects") =
        Value::Array(vec![Value::String("network".to_owned())]);
    let mut bytes = vec![];
    json::encode(&value, &mut bytes);
    assert!(normalize_document(&bytes, json_limits()).is_err());
    // 即使内部调用传入与 P1 前提不一致的树，效果声明规则也拒绝。
    let mut builder = rules::Builder::new(limits());
    assert!(matches!(
        builder.document(&value, &document),
        Err(EffectError::InvalidConstruct {
            reason: "nonempty effects",
            ..
        })
    ));
    let mut value = json::parse(document.canonical_bytes(), json_limits()).unwrap();
    let Value::Object(root) = &mut value else {
        unreachable!()
    };
    let Value::Array(nodes) = declarations::member_mut(root, "nodes") else {
        unreachable!()
    };
    let Value::Object(entry) = &mut nodes[0] else {
        unreachable!()
    };
    let Value::Object(definition) = declarations::member_mut(entry, "definition") else {
        unreachable!()
    };
    definition.push((
        "capability".to_owned(),
        Value::String("filesystem".to_owned()),
        0,
    ));
    let mut builder = rules::Builder::new(limits());
    assert!(matches!(
        builder.document(&value, &document),
        Err(EffectError::InvalidConstruct {
            reason: "non-closed construct",
            ..
        })
    ));
}
