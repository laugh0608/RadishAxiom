use super::*;
#[path = "tests_model.rs"]
mod model;
use crate::{
    document::check_canonical_document,
    obligations::{ObligationLimits, ObligationProfile, generate_obligations},
};
use std::path::PathBuf;
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn limits() -> ReplayLimits {
    ReplayLimits {
        ir_json: JsonLimits {
            max_input_bytes: 32_000_000,
            max_values: 2_000_000,
            max_nesting: 128,
        },
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
fn generator() -> GeneratorIdentity {
    GeneratorIdentity::new(&format!("sha256:{}", "a".repeat(64))).unwrap()
}
fn setup(path: &str) -> (CanonicalDocument, ObligationSet) {
    let l = limits();
    let d =
        check_canonical_document(&std::fs::read(root().join(path)).unwrap(), l.ir_json).unwrap();
    let s = generate_obligations(
        &d,
        ObligationProfile::VerificationV0_2,
        ObligationLimits {
            ir_json: l.ir_json,
            max_obligations: 100_000,
            max_definition_bytes: 32_000_000,
            max_path_bytes: 16_000_000,
            max_output_bytes: 32_000_000,
        },
    )
    .unwrap();
    (d, s)
}
fn replay(
    d: &CanonicalDocument,
    s: &ObligationSet,
    id: &str,
    w: &[u8],
    l: ReplayLimits,
) -> Result<TargetReplayObservation> {
    replay_target(
        ReplayProfile::MapFilterV0_1,
        ReplayInput {
            document: d,
            obligations: s,
            obligation_id: id,
            generator: &generator(),
            world: ReplayWorldInput::Provided(w),
        },
        l,
    )
}
fn temp(name: &str) -> PathBuf {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!(
        "radishaxiom-p4b-{name}-{}-{stamp}",
        std::process::id()
    ));
    std::fs::create_dir(&dir).unwrap();
    dir
}
#[test]
fn four_profiles_match_independent_finite_semantics() {
    let dir = temp("differential");
    let generated = std::process::Command::new("python3")
        .arg(root().join("scripts/generate-p4b-replay-vectors.py"))
        .arg(&dir)
        .output()
        .unwrap();
    assert!(
        generated.status.success(),
        "{}",
        String::from_utf8_lossy(&generated.stderr)
    );
    let cases = json::parse(
        &std::fs::read(dir.join("manifest.jcs")).unwrap(),
        limits().ir_json,
    )
    .unwrap();
    let mut count = 0;
    for c in array(&cases) {
        let (d, s) = setup(text(c, "ir"));
        for item in array(get(c, "items")) {
            let w = std::fs::read(dir.join(text(item, "world"))).unwrap();
            let details = json::parse(
                &std::fs::read(dir.join(text(item, "details"))).unwrap(),
                limits().ir_json,
            )
            .unwrap();
            let mut details = array(&details).iter();
            for (id, expected) in array(get(c, "targets"))
                .iter()
                .zip(array(get(item, "expected")))
            {
                let result = replay(&d, &s, string(id), &w, limits()).unwrap_or_else(|e| {
                    panic!(
                        "{} {} {}: {e}",
                        text(c, "name"),
                        text(item, "world"),
                        string(id)
                    )
                });
                let decoded = json::parse(result.result_bytes(), limits().ir_json).unwrap();
                assert_eq!(
                    text(&decoded, "kind"),
                    string(expected),
                    "{} {} {}",
                    text(c, "name"),
                    text(item, "world"),
                    string(id)
                );
                let mut expected_bytes = Vec::new();
                json::encode(details.next().unwrap(), &mut expected_bytes);
                assert_eq!(
                    result.result_bytes(),
                    expected_bytes,
                    "{} {} {}",
                    text(c, "name"),
                    text(item, "world"),
                    string(id)
                );
                count += 1;
            }
        }
    }
    assert_eq!(count, 29153);
    eprintln!("P4-B {count} finite observations matched Python; no solver / proof");
    std::fs::remove_dir_all(dir).unwrap();
}

fn hand_dir() -> &'static std::path::Path {
    static DIR: std::sync::OnceLock<PathBuf> = std::sync::OnceLock::new();
    DIR.get_or_init(|| {
        let dir = temp("hand");
        let r = std::process::Command::new("python3")
            .arg(root().join("scripts/generate-p4b-hand-vectors.py"))
            .arg(&dir)
            .output()
            .unwrap();
        assert!(r.status.success(), "{}", String::from_utf8_lossy(&r.stderr));
        dir
    })
    .as_path()
}
fn hand(name: &str) -> (CanonicalDocument, ObligationSet, Vec<u8>) {
    let dir = hand_dir();
    let (d, s) = setup(dir.join(format!("{name}.ir.jcs")).to_str().unwrap());
    (
        d,
        s,
        std::fs::read(dir.join(format!("{name}.world.jcs"))).unwrap(),
    )
}
fn guarantee(s: &ObligationSet) -> &str {
    s.obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::ContractGuarantee)
        .unwrap()
        .id()
}
fn encoded(v: &Value) -> Vec<u8> {
    let mut bytes = Vec::new();
    json::encode(v, &mut bytes);
    bytes
}
fn result(o: &TargetReplayObservation) -> Value {
    json::parse(o.result_bytes(), limits().ir_json).unwrap()
}
fn member_mut<'a>(v: &'a mut Value, key: &str) -> &'a mut Value {
    let Value::Object(m) = v else {
        panic!("object")
    };
    &mut m.iter_mut().find(|(k, _, _)| k == key).unwrap().1
}
fn array_mut(v: &mut Value) -> &mut Vec<Value> {
    let Value::Array(a) = v else { panic!("array") };
    a
}
fn row_mut(v: &mut Value) -> &mut Value {
    &mut array_mut(member_mut(&mut array_mut(v)[0], "rows"))[0]
}
fn field_mut<'a>(row: &'a mut Value, name: &str) -> &'a mut Value {
    let f = array_mut(member_mut(row, "fields"))
        .iter_mut()
        .find(|f| text(f, "name") == name)
        .unwrap();
    member_mut(f, "value")
}
#[test]
fn original_ax_b01_and_hand_distinctions_match_exact_independent_witnesses() {
    let names = json::parse(
        &std::fs::read(hand_dir().join("names.jcs")).unwrap(),
        limits().ir_json,
    )
    .unwrap();
    let mut count = 0;
    for name in array(&names) {
        let name = string(name);
        let (d, s, w) = hand(name);
        let expected = json::parse(
            &std::fs::read(hand_dir().join(format!("{name}.expected.jcs"))).unwrap(),
            limits().ir_json,
        )
        .unwrap();
        for (id, detail) in array(get(&expected, "targets"))
            .iter()
            .zip(array(get(&expected, "results")))
        {
            let observed = replay(&d, &s, string(id), &w, limits()).unwrap();
            assert_eq!(
                observed.result_bytes(),
                encoded(detail),
                "{name} {}",
                string(id)
            );
            count += 1;
        }
    }
    eprintln!("P4-B {count} hand target results matched; AX-B01 capacity unchanged");
}
#[test]
fn deep_record_and_dependency_chain_are_iterative() {
    let (d, s, w) = hand("deep-record");
    let o = replay(&d, &s, guarantee(&s), &w, limits()).unwrap();
    assert_eq!(o.outcome(), ReplayOutcome::TargetNotViolated);
    assert!(o.usage().world_depth > 15000);
    let mut l = limits();
    l.world_depth = o.usage().world_depth - 1;
    assert!(matches!(
        replay(&d, &s, guarantee(&s), &w, l),
        Err(ReplayError::ResourceLimit {
            resource: ReplayResource::WorldDepth,
            ..
        })
    ));
    let (d, s, w) = hand("deep-graph");
    let node = std::fs::read_to_string(hand_dir().join("deep-graph.target.txt")).unwrap();
    let id = s
        .obligations()
        .iter()
        .find(|o| {
            o.kind() == ObligationKind::Totality
                && text(
                    get(
                        &json::parse(o.canonical_definition(), limits().ir_json).unwrap(),
                        "subject",
                    ),
                    "id",
                ) == node
        })
        .unwrap()
        .id();
    let o = replay(&d, &s, id, &w, limits()).unwrap();
    assert_eq!(o.outcome(), ReplayOutcome::TargetViolated);
    let mut b = Budget::new(limits());
    let (j, root) = Json::parse(o.result_bytes(), &mut b).unwrap();
    let mut cause = j.get(j.get(root, "witness").unwrap(), "cause").unwrap();
    let mut depth = 0;
    while j.text(cause, "kind").unwrap() == "dependency" {
        depth += 1;
        cause = j.get(cause, "cause").unwrap();
    }
    assert_eq!(depth, 1500);
    assert_eq!(j.text(cause, "kind").unwrap(), "range");
}
#[test]
fn world_format_and_input_failures_are_distinct() {
    let (d, s, w) = hand("foreign-key-1");
    let id = guarantee(&s);
    let original = json::parse(&w, limits().ir_json).unwrap();
    for kind in ["range", "enum-member", "duplicate-key", "capacity"] {
        let mut v = copy(&original);
        match kind {
            "range" => {
                *member_mut(field_mut(row_mut(&mut v), "x"), "value") = Value::String("999".into());
            }
            "enum-member" => {
                *member_mut(field_mut(row_mut(&mut v), "mode"), "member") =
                    Value::String("unknown".into());
            }
            "duplicate-key" => {
                let rows = array_mut(member_mut(&mut array_mut(&mut v)[0], "rows"));
                rows.push(copy(&rows[0]));
            }
            _ => {
                let rows = array_mut(member_mut(&mut array_mut(&mut v)[0], "rows"));
                let base = copy(&rows[0]);
                rows.clear();
                for k in ["0", "1", "2"] {
                    let mut r = copy(&base);
                    *member_mut(field_mut(&mut r, "key"), "value") = Value::String(k.into());
                    rows.push(r);
                }
            }
        }
        let o = replay(&d, &s, id, &encoded(&v), limits()).unwrap();
        assert_eq!(o.outcome(), ReplayOutcome::InputRejected);
        assert_eq!(text(&result(&o), "reason"), kind);
    }
    for replacement in ["01", "-0", "+1", "1.0", ""] {
        let mut v = copy(&original);
        *member_mut(field_mut(row_mut(&mut v), "key"), "value") = Value::String(replacement.into());
        assert!(matches!(
            replay(&d, &s, id, &encoded(&v), limits()),
            Err(ReplayError::WorldFormat { .. })
        ));
    }
    let mut v = copy(&original);
    let fields = array_mut(member_mut(row_mut(&mut v), "fields"));
    fields.swap(0, 1);
    assert!(matches!(
        replay(&d, &s, id, &encoded(&v), limits()),
        Err(ReplayError::WorldFormat { .. })
    ));
    let mut v = copy(&original);
    let rows = array_mut(member_mut(&mut array_mut(&mut v)[0], "rows"));
    let mut low = copy(&rows[0]);
    *member_mut(field_mut(&mut low, "key"), "value") = Value::String("0".into());
    rows.push(low);
    assert!(matches!(
        replay(&d, &s, id, &encoded(&v), limits()),
        Err(ReplayError::NonCanonicalWorld { .. })
    ));
    let mut v = original;
    array_mut(member_mut(row_mut(&mut v), "fields")).pop();
    assert!(matches!(
        replay(&d, &s, id, &encoded(&v), limits()),
        Err(ReplayError::WorldFormat { .. })
    ));
    for bad in [
        b"[]\n".as_slice(),
        b"[ ]",
        b"null",
        b"[0]",
        b"[{\"x\":true,\"x\":false}]",
        b"[\"\\uD800\"]",
        b"[\"\\u0061\"]",
        b"\xef\xbb\xbf[]",
        b"[\xff]",
    ] {
        assert!(replay(&d, &s, id, bad, limits()).is_err(), "{bad:?}");
    }
}
#[test]
fn strict_observation_rebuild_binds_world_target_generator_and_budget() {
    let (d, s, w) = hand("ax-b01-wrong-add");
    let id = guarantee(&s);
    let o = replay(&d, &s, id, &w, limits()).unwrap();
    let check = |bytes: &[u8], world: &[u8], target: &str, l: ReplayLimits| {
        check_target_replay(
            bytes,
            ReplayProfile::MapFilterV0_1,
            ReplayInput {
                document: &d,
                obligations: &s,
                obligation_id: target,
                generator: &generator(),
                world: ReplayWorldInput::Provided(world),
            },
            l,
        )
    };
    check(o.canonical_bytes(), &w, id, limits()).unwrap();
    let parsed = json::parse(o.canonical_bytes(), limits().ir_json).unwrap();
    for field in [
        "binding",
        "source",
        "world_raw_digest",
        "result",
        "limits",
        "usage",
        "rule_digest",
    ] {
        let mut v = copy(&parsed);
        *member_mut(&mut v, field) = Value::Bool(true);
        assert!(matches!(
            check(&encoded(&v), &w, id, limits()),
            Err(ReplayError::NonCanonicalObservation { .. })
        ));
    }
    let mut world = json::parse(&w, limits().ir_json).unwrap();
    *member_mut(field_mut(row_mut(&mut world), "discount_cents"), "value") =
        Value::String("0".into());
    assert!(matches!(
        check(o.canonical_bytes(), &encoded(&world), id, limits()),
        Err(ReplayError::NonCanonicalObservation { .. })
    ));
    let other = s
        .obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::Totality)
        .unwrap()
        .id();
    assert!(matches!(
        check(o.canonical_bytes(), &w, other, limits()),
        Err(ReplayError::NonCanonicalObservation { .. })
    ));
    let mut l = limits();
    l.rows -= 1;
    assert!(matches!(
        check(o.canonical_bytes(), &w, id, l),
        Err(ReplayError::NonCanonicalObservation { .. })
    ));
    let mut l = limits();
    l.output_bytes = 1;
    assert!(matches!(
        check(o.canonical_bytes(), &w, id, l),
        Err(ReplayError::ResourceLimit {
            resource: ReplayResource::OutputBytes,
            ..
        })
    ));
    let (d2, _, _) = hand("ax-b01-correct");
    assert!(matches!(
        replay(&d2, &s, id, &w, limits()),
        Err(ReplayError::BindingMismatch)
    ));
    assert!(matches!(
        replay(&d, &s, "missing", &w, limits()),
        Err(ReplayError::UnknownObligation(_))
    ));
    let check_id = s
        .obligations()
        .iter()
        .find(|o| o.kind().expectation() == "check")
        .unwrap()
        .id();
    assert!(matches!(
        replay(&d, &s, check_id, &w, limits()),
        Err(ReplayError::NotProve(_))
    ));
    let unsupported = s
        .obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::EffectEmpty)
        .unwrap()
        .id();
    assert!(matches!(
        replay(&d, &s, unsupported, &w, limits()),
        Err(ReplayError::UnsupportedKind(_))
    ));
    assert!(matches!(
        ReplayProfile::from_id("axiom-p4-map-filter-replay-v0.0"),
        Err(ReplayError::UnsupportedProfile)
    ));
}
#[test]
fn every_resource_has_an_exact_boundary_and_checked_overflow() {
    let (d, s, w) = hand("ax-b01-wrong-add");
    let id = guarantee(&s);
    macro_rules! boundary {
        ($field:ident,$resource:ident) => {{
            let mut l = limits();
            for _ in 0..10 {
                let o = replay(&d, &s, id, &w, l).unwrap();
                let used = o.usage().$field;
                assert!(used > 0, stringify!($field));
                if l.$field == used {
                    break;
                }
                l.$field = used;
            }
            let o = replay(&d, &s, id, &w, l).unwrap();
            assert_eq!(l.$field, o.usage().$field, stringify!($field));
            l.$field -= 1;
            assert!(
                matches!(
                    replay(&d, &s, id, &w, l),
                    Err(ReplayError::ResourceLimit {
                        resource: ReplayResource::$resource,
                        ..
                    })
                ),
                stringify!($field)
            );
        }};
    }
    boundary!(world_bytes, WorldBytes);
    boundary!(world_nodes, WorldNodes);
    boundary!(world_depth, WorldDepth);
    boundary!(type_items, TypeItems);
    boundary!(rows, Rows);
    boundary!(value_cells, ValueCells);
    boundary!(evaluation_steps, EvaluationSteps);
    boundary!(comparisons, Comparisons);
    boundary!(integer_digits, IntegerDigits);
    boundary!(digit_work, DigitWork);
    boundary!(text_bytes, TextBytes);
    boundary!(path_bytes, PathBytes);
    boundary!(output_bytes, OutputBytes);
    let mut b = Budget::new(limits());
    b.usage.value_cells = usize::MAX;
    assert!(matches!(
        b.charge(ReplayResource::ValueCells, 1),
        Err(ReplayError::ResourceLimit {
            resource: ReplayResource::ValueCells,
            ..
        })
    ));
}
#[test]
fn decimal_math_matches_host_small_domain_and_hundred_digit_hand_cases() {
    let mut b = Budget::new(limits());
    for a in -100..=100 {
        for c in -100..=100 {
            let aa = arithmetic::parse(&a.to_string(), &mut b).unwrap();
            let cc = arithmetic::parse(&c.to_string(), &mut b).unwrap();
            for sub in [false, true] {
                assert_eq!(
                    arithmetic::calculate(&aa, &cc, sub, &mut b)
                        .unwrap()
                        .as_str(),
                    (if sub { a - c } else { a + c }).to_string()
                );
            }
        }
    }
    for (a, c, sub, expected) in [
        (
            "9".repeat(100),
            "1".into(),
            false,
            format!("1{}", "0".repeat(100)),
        ),
        (
            format!("-{}", "9".repeat(100)),
            "9".repeat(100),
            false,
            "0".into(),
        ),
        (
            format!("1{}", "0".repeat(100)),
            "1".into(),
            true,
            "9".repeat(100),
        ),
    ] {
        let a = arithmetic::parse(&a, &mut b).unwrap();
        let c = arithmetic::parse(&c, &mut b).unwrap();
        assert_eq!(
            arithmetic::calculate(&a, &c, sub, &mut b).unwrap().as_str(),
            expected
        );
    }
}

fn copy(v: &Value) -> Value {
    json::parse(&encoded(v), limits().ir_json).unwrap()
}

#[test]
fn independent_checker_rejects_binding_input_budget_and_witness_mutations() {
    let (d, s, w) = hand("ax-b01-wrong-add");
    let id = guarantee(&s);
    let o = replay(&d, &s, id, &w, limits()).unwrap();
    let parsed = json::parse(o.canonical_bytes(), limits().ir_json).unwrap();
    let input = Value::Object(vec![
        (
            "generator".into(),
            Value::String(generator().source_digest().into()),
            0,
        ),
        ("limits".into(), copy(get(&parsed, "limits")), 0),
        ("source".into(), copy(get(&parsed, "source")), 0),
        ("target".into(), Value::String(id.into()), 0),
    ]);
    let dir = temp("checker");
    for (name, bytes) in [
        ("ir.jcs", d.canonical_bytes()),
        ("p2.jcs", s.canonical_bytes()),
        ("world.jcs", w.as_slice()),
        ("observation.jcs", o.canonical_bytes()),
        ("input.jcs", encoded(&input).as_slice()),
    ] {
        std::fs::write(dir.join(name), bytes).unwrap();
    }
    let check = std::process::Command::new("python3")
        .arg(root().join("scripts/check-p4b-replay.py"))
        .arg(&dir)
        .arg("--mutations")
        .output()
        .unwrap();
    assert!(
        check.status.success(),
        "{}; retained at {}",
        String::from_utf8_lossy(&check.stderr),
        dir.display()
    );
    eprintln!("{}", String::from_utf8_lossy(&check.stdout));
    std::fs::remove_dir_all(dir).unwrap();
}

#[test]
fn injected_local_relations_keep_multiplicity_and_every_key_component() {
    let (d, s, w) = hand("foreign-key-1");
    let ir = json::parse(d.canonical_bytes(), limits().ir_json).unwrap();
    let target = s
        .obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::KeyCardinality)
        .unwrap();
    let def = json::parse(target.canonical_definition(), limits().ir_json).unwrap();
    let mut b = Budget::new(limits());
    let mut e = engine::Engine::new(&d, &ir, &def, ObligationKind::KeyCardinality, &mut b).unwrap();
    let (j, root) = Json::parse(&w, &mut b).unwrap();
    e.run(&j, root, &mut b).unwrap();
    let target = e.target_anchor;
    let row = e.computed[target].rows[0];
    e.computed.get_mut(target).unwrap().rows = std::sync::Arc::new(vec![row, row]);
    let (obs, outcome) = e.target(&mut b).unwrap();
    assert_eq!(outcome, ReplayOutcome::TargetViolated);
    assert!(matches!(
        obs,
        engine::Observation::Violated {
            detail: engine::Detail::Cardinality {
                reason: Some("duplicate-key"),
                ..
            }
        }
    ));
    let mut ids = Vec::new();
    for n in ["0", "1", "2"] {
        let v = arithmetic::parse(n, &mut b).unwrap();
        ids.push(e.push(engine::Val::Int(v), &mut b).unwrap());
    }
    let key = |a: usize, c: usize| vec![ids[a], ids[c]];
    let cases = [
        (vec![], vec![], None),
        (vec![key(0, 0), key(0, 1)], vec![key(0, 1), key(0, 0)], None),
        (vec![key(0, 0)], vec![], Some(("forward", 0))),
        (vec![], vec![key(0, 0)], Some(("backward", 0))),
        (
            vec![key(0, 0)],
            vec![key(0, 0), key(0, 0)],
            Some(("forward", 2)),
        ),
        (
            vec![key(0, 0), key(0, 0)],
            vec![key(0, 0)],
            Some(("backward", 2)),
        ),
        (vec![key(0, 0)], vec![key(0, 1)], Some(("forward", 0))),
    ];
    for (mut a, mut c, expected) in cases {
        let got = e.coverage(&mut a, &mut c, &mut b).unwrap();
        assert_eq!(got.map(|(d, _, n)| (d, n)), expected);
    }
    let a = e.push(engine::Val::Text("é".into()), &mut b).unwrap();
    let c = e
        .push(engine::Val::Text("e\u{301}".into()), &mut b)
        .unwrap();
    assert_eq!(
        e.coverage(&mut [vec![a]], &mut [vec![c]], &mut b)
            .unwrap()
            .unwrap()
            .0,
        "forward"
    );
}

#[test]
fn unsupported_whole_graph_and_unselected_contract_branches_are_rejected() {
    for path in [
        "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b02-wrong-region-join.jcs",
        "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b03-wrong-single-group.jcs",
        hand_dir().join("unsupported.ir.jcs").to_str().unwrap(),
    ] {
        let (d, s) = setup(path);
        assert!(
            matches!(
                replay(&d, &s, guarantee(&s), b"[]", limits()),
                Err(ReplayError::UnsupportedFeature { .. })
            ),
            "{path}"
        );
    }
}

#[test]
fn large_text_prefix_and_integer_refusals_are_resources_not_faults() {
    let (d, s, w) = hand("ax-b01-correct");
    let id = guarantee(&s);
    let mut world = json::parse(&w, limits().ir_json).unwrap();
    let rows = array_mut(member_mut(&mut array_mut(&mut world)[0], "rows"));
    for (i, row) in rows.iter_mut().enumerate() {
        *member_mut(field_mut(row, "order_id"), "value") =
            Value::String(format!("{}{i}", "a".repeat(20000)));
    }
    let bytes = encoded(&world);
    let ok = replay(&d, &s, id, &bytes, limits()).unwrap();
    assert_eq!(ok.outcome(), ReplayOutcome::TargetNotViolated);
    assert!(ok.usage().text_bytes > 120000);
    let mut l = limits();
    l.text_bytes = 120000;
    assert!(matches!(
        replay(&d, &s, id, &bytes, l),
        Err(ReplayError::ResourceLimit {
            resource: ReplayResource::TextBytes,
            ..
        })
    ));
    *member_mut(field_mut(row_mut(&mut world), "discount_cents"), "value") =
        Value::String("9".repeat(10001));
    assert!(matches!(
        replay(&d, &s, id, &encoded(&world), limits()),
        Err(ReplayError::ResourceLimit {
            resource: ReplayResource::IntegerDigits,
            ..
        })
    ));
}
