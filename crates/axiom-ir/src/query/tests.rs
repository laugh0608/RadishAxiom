use super::*;

mod cardinality;
mod totality;
use crate::{
    declarations,
    document::{check_canonical_document, normalize_document},
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
fn p2_limits() -> ObligationLimits {
    ObligationLimits {
        ir_json: json_limits(),
        max_obligations: 100_000,
        max_definition_bytes: 16_000_000,
        max_path_bytes: 8_000_000,
        max_output_bytes: 24_000_000,
    }
}
fn limits() -> QueryLimits {
    QueryLimits {
        ir_json: json_limits(),
        max_input_slots: 10_000,
        max_value_cells: 10_000_000,
        max_expression_instances: 1_000_000,
        max_slot_comparisons: 1_000_000,
        max_smt_nodes: 10_000_000,
        max_output_bytes: 100_000_000,
    }
}
fn identity() -> GeneratorIdentity {
    GeneratorIdentity::new(&format!("sha256:{}", "a".repeat(64))).unwrap()
}
fn doc(name: &str) -> CanonicalDocument {
    check_canonical_document(
        &std::fs::read(root().join(format!("contracts/map-filter-query-v0.1/inputs/{name}.jcs")))
            .unwrap(),
        json_limits(),
    )
    .unwrap()
}
fn set(doc: &CanonicalDocument) -> ObligationSet {
    generate_obligations(doc, ObligationProfile::VerificationV0_2, p2_limits()).unwrap()
}
fn guarantee(set: &ObligationSet) -> &str {
    set.obligations()
        .iter()
        .find(|o| o.kind() == ObligationKind::ContractGuarantee)
        .unwrap()
        .id()
}
fn s(value: impl Into<String>) -> Value {
    Value::String(value.into())
}
fn obj(fields: Vec<(&str, Value)>) -> Value {
    Value::Object(
        fields
            .into_iter()
            .map(|(key, value)| (key.to_owned(), value, 0))
            .collect(),
    )
}
fn symbols(query: &EncodedQuery) -> Vec<u8> {
    symbol_list(query.symbols())
}
fn symbol_list(symbols: &[QuerySymbol]) -> Vec<u8> {
    let value = Value::Array(
        symbols
            .iter()
            .map(|symbol| {
                let origin = match symbol.origin() {
                    SymbolOrigin::TextLiteral(value) => {
                        obj(vec![("kind", s("text")), ("value", s(value))])
                    }
                    SymbolOrigin::Input {
                        interface,
                        slot,
                        component,
                    } => obj(vec![
                        ("kind", s("input")),
                        ("interface", s(interface.as_ref())),
                        ("slot", s(slot.to_string())),
                        (
                            "component",
                            s(component
                                .map(|n| n.to_string())
                                .unwrap_or("active".to_owned())),
                        ),
                    ]),
                };
                obj(vec![
                    ("name", s(symbol.name())),
                    ("sort", s(symbol.sort())),
                    ("origin", origin),
                ])
            })
            .collect(),
    );
    let mut bytes = Vec::new();
    json::encode(&value, &mut bytes);
    bytes
}

#[test]
fn actual_smt_text_matches_independent_concrete_semantics() {
    compare_semantics(
        QueryProfile::MapFilterV0_1,
        "v0.1",
        "check-p3-query-semantics.py",
    );
}

fn compare_semantics(profile: QueryProfile, version: &str, script: &str) {
    let vectors =
        std::fs::read(root().join(format!("contracts/map-filter-query-{version}/cases.json")))
            .unwrap();
    let baseline: std::collections::BTreeMap<_, _> =
        include_str!("../../../../contracts/map-filter-query-v0.2/v0.1-baseline.tsv")
            .lines()
            .map(|line| {
                let columns: Vec<_> = line.split('\t').collect();
                (
                    columns[1],
                    (columns[2], columns[3].parse::<usize>().unwrap()),
                )
            })
            .collect();
    // 材料含 number / null，使用 Python 转换为本 crate JSON 子集仅供测试索引。
    let directory = std::env::temp_dir().join(format!(
        "radishaxiom-p3-semantics-{version}-{}",
        std::process::id()
    ));
    std::fs::create_dir(&directory).unwrap();
    let manifest = std::process::Command::new("python3").arg("-c").arg(
        "import json,sys; d=json.load(sys.stdin); print(json.dumps([{'name':c['name'],'ir':c['ir'],'ids':[o['id'] for o in c['targets']]} for c in d['cases']]))"
    ).stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).spawn().and_then(|mut child| {
        use std::io::Write;
        child.stdin.take().unwrap().write_all(&vectors)?; child.wait_with_output()
    }).unwrap();
    assert!(manifest.status.success());
    let cases = json::parse(&manifest.stdout, json_limits()).unwrap();
    let previous: std::collections::BTreeMap<_, _> =
        include_str!("../../../../contracts/map-filter-query-v0.3/v0.2-baseline.tsv")
            .lines()
            .map(|line| {
                let columns: Vec<_> = line.split('\t').collect();
                let n = |i: usize| columns[i].parse::<usize>().unwrap();
                (
                    columns[1],
                    (
                        columns[2],
                        QueryUsage {
                            input_slots: n(3),
                            value_cells: n(4),
                            expression_instances: n(5),
                            slot_comparisons: n(6),
                            smt_nodes: n(7),
                            output_bytes: n(8),
                        },
                    ),
                )
            })
            .collect();
    let mut previous_seen = std::collections::BTreeSet::new();
    let mut query_count = 0;
    let mut legacy_seen = std::collections::BTreeSet::new();
    for case in array(&cases) {
        let document = check_canonical_document(
            &std::fs::read(root().join(text(case, "ir"))).unwrap(),
            json_limits(),
        )
        .unwrap_or_else(|e| {
            panic!(
                "{}: {e}; artifacts retained at {}",
                text(case, "name"),
                directory.display()
            )
        });
        let set = set(&document);
        for (index, id) in array(get(case, "ids")).iter().enumerate() {
            let query =
                encode_query(profile, &document, &set, string(id), &identity(), limits()).unwrap();
            assert_eq!(query.binding().encoding_profile(), profile.as_str());
            if let Some(&(digest, bytes)) = baseline.get(string(id)) {
                legacy_seen.insert(string(id));
                assert_eq!(query.artifact_digest(), digest, "legacy SMT bytes drift");
                assert_eq!(query.bytes().len(), bytes);
            }
            if let Some(&(digest, usage)) = previous.get(string(id)) {
                previous_seen.insert(string(id));
                assert_eq!(query.artifact_digest(), digest, "v0.2 SMT bytes drift");
                assert_eq!(query.usage(), usage, "v0.2 budget drift");
                if profile == QueryProfile::MapFilterV0_3 {
                    let old = encode_query(
                        QueryProfile::MapFilterV0_2,
                        &document,
                        &set,
                        string(id),
                        &identity(),
                        limits(),
                    )
                    .unwrap();
                    assert_eq!(old.bytes(), query.bytes());
                    assert_eq!(old.symbols(), query.symbols());
                    assert_eq!(old.usage(), query.usage());
                    assert_ne!(old.binding(), query.binding());
                }
            }
            let stem = directory.join(format!("{}-{index}", text(case, "name")));
            std::fs::write(stem.with_extension("smt2"), query.bytes()).unwrap();
            std::fs::write(stem.with_extension("json"), symbols(&query)).unwrap();
            query_count += 1;
        }
    }
    assert_eq!(legacy_seen, baseline.keys().copied().collect());
    if version != "v0.1" {
        assert_eq!(previous_seen, previous.keys().copied().collect());
    }
    let result = std::process::Command::new("python3")
        .arg(root().join("scripts").join(script))
        .arg(&directory)
        .output()
        .unwrap();
    if !result.status.success() {
        panic!(
            "independent SMT comparison failed; artifacts retained at {}\n{}\n{}",
            directory.display(),
            String::from_utf8_lossy(&result.stdout),
            String::from_utf8_lossy(&result.stderr)
        );
    }
    eprintln!(
        "{} actual queries: {}",
        query_count,
        String::from_utf8_lossy(&result.stdout)
    );
    // 仅删除该测试本次创建的精确目录；失败保留以便诊断。
    std::fs::remove_dir_all(directory).unwrap();
}

#[test]
fn bindings_tampering_and_deterministic_bytes_are_checked() {
    let minimum = doc("minimal");
    let minimum_set = set(&minimum);
    let minimum_query = encode_query(
        QueryProfile::MapFilterV0_1,
        &minimum,
        &minimum_set,
        guarantee(&minimum_set),
        &identity(),
        limits(),
    )
    .unwrap();
    assert_eq!(
        minimum_query.bytes(),
        std::fs::read(root().join("contracts/map-filter-query-v0.1/expected/minimal.smt2"))
            .unwrap()
    );
    let document = doc("int-add");
    let set = set(&document);
    let target = guarantee(&set);
    let generator = identity();
    let query = encode_query(
        QueryProfile::MapFilterV0_1,
        &document,
        &set,
        target,
        &generator,
        limits(),
    )
    .unwrap();
    assert_eq!(
        check_query(
            QueryProfile::MapFilterV0_1,
            query.bytes(),
            &document,
            &set,
            target,
            &generator,
            limits()
        )
        .unwrap(),
        query
    );
    let mut bytes = query.bytes().to_vec();
    bytes.push(b'\n');
    assert!(matches!(
        check_query(
            QueryProfile::MapFilterV0_1,
            &bytes,
            &document,
            &set,
            target,
            &generator,
            limits()
        ),
        Err(QueryError::NonCanonicalQuery { .. })
    ));
    let other = doc("int-sub");
    assert!(matches!(
        encode_query(
            QueryProfile::MapFilterV0_1,
            &other,
            &set,
            target,
            &generator,
            limits()
        ),
        Err(QueryError::BindingMismatch)
    ));
    assert!(matches!(
        encode_query(
            QueryProfile::MapFilterV0_1,
            &document,
            &set,
            "missing",
            &generator,
            limits()
        ),
        Err(QueryError::UnknownObligation(_))
    ));
    assert!(matches!(
        GeneratorIdentity::new("0.0.0"),
        Err(QueryError::InvalidGeneratorIdentity)
    ));
    let mut reversed = json::parse(document.canonical_bytes(), json_limits()).unwrap();
    let Value::Object(root) = &mut reversed else {
        unreachable!()
    };
    for name in [
        "nodes",
        "contracts",
        "record_types",
        "table_types",
        "enum_types",
        "outputs",
    ] {
        let Value::Array(values) = declarations::member_mut(root, name) else {
            unreachable!()
        };
        values.reverse();
    }
    let mut bytes = Vec::new();
    json::encode(&reversed, &mut bytes);
    let reversed = normalize_document(&bytes, json_limits()).unwrap();
    assert_eq!(
        encode_query(
            QueryProfile::MapFilterV0_1,
            &reversed,
            &set,
            target,
            &generator,
            limits()
        )
        .unwrap(),
        query
    );
    let changed = GeneratorIdentity::new(&format!("sha256:{}", "b".repeat(64))).unwrap();
    let changed = encode_query(
        QueryProfile::MapFilterV0_1,
        &document,
        &set,
        target,
        &changed,
        limits(),
    )
    .unwrap();
    assert_eq!(changed.bytes(), query.bytes());
    assert_ne!(changed.binding(), query.binding());
}

#[test]
fn every_accumulated_budget_accepts_exact_limit_and_rejects_one_less() {
    let document = doc("lookup-identity");
    let set = set(&document);
    let target = guarantee(&set);
    let query = encode_query(
        QueryProfile::MapFilterV0_1,
        &document,
        &set,
        target,
        &identity(),
        limits(),
    )
    .unwrap();
    let used = query.usage();
    let exact = QueryLimits {
        ir_json: json_limits(),
        max_input_slots: used.input_slots,
        max_value_cells: used.value_cells,
        max_expression_instances: used.expression_instances,
        max_slot_comparisons: used.slot_comparisons,
        max_smt_nodes: used.smt_nodes,
        max_output_bytes: used.output_bytes,
    };
    assert_eq!(
        encode_query(
            QueryProfile::MapFilterV0_1,
            &document,
            &set,
            target,
            &identity(),
            exact
        )
        .unwrap(),
        query
    );
    for resource in [
        QueryResource::InputSlots,
        QueryResource::ValueCells,
        QueryResource::ExpressionInstances,
        QueryResource::SlotComparisons,
        QueryResource::SmtNodes,
        QueryResource::OutputBytes,
    ] {
        let mut reduced = exact;
        match resource {
            QueryResource::InputSlots => reduced.max_input_slots -= 1,
            QueryResource::ValueCells => reduced.max_value_cells -= 1,
            QueryResource::ExpressionInstances => reduced.max_expression_instances -= 1,
            QueryResource::SlotComparisons => reduced.max_slot_comparisons -= 1,
            QueryResource::SmtNodes => reduced.max_smt_nodes -= 1,
            QueryResource::OutputBytes => reduced.max_output_bytes -= 1,
        }
        assert!(
            matches!(encode_query(QueryProfile::MapFilterV0_1, &document, &set, target, &identity(), reduced),
            Err(QueryError::ResourceLimit { resource: actual, .. }) if actual == resource),
            "{resource:?}"
        );
    }
}

#[test]
fn expansion_preflight_and_deep_reference_graphs_are_bounded() {
    let load = |name: &str| {
        check_canonical_document(
            &std::fs::read(root().join(format!(
                "contracts/map-filter-query-v0.1/resource-inputs/{name}.jcs"
            )))
            .unwrap(),
            json_limits(),
        )
        .unwrap()
    };
    let nested = load("nested-expansion");
    let nested_set = set(&nested);
    assert!(matches!(
        encode_query(
            QueryProfile::MapFilterV0_1,
            &nested,
            &nested_set,
            guarantee(&nested_set),
            &identity(),
            limits()
        ),
        Err(QueryError::ResourceLimit {
            resource: QueryResource::ExpressionInstances,
            ..
        })
    ));
    let deep = load("deep-type-and-graph");
    let deep_set = set(&deep);
    let query = encode_query(
        QueryProfile::MapFilterV0_1,
        &deep,
        &deep_set,
        guarantee(&deep_set),
        &identity(),
        limits(),
    )
    .unwrap();
    assert_eq!(query.usage().input_slots, 1);
    assert_eq!(query.usage().expression_instances, 5001);
    assert_eq!(
        query
            .symbols()
            .iter()
            .filter(|s| matches!(s.origin(), SymbolOrigin::Input { .. }))
            .count(),
        3
    );
    let empty = doc("zero-capacity");
    let empty_set = set(&empty);
    let mut zero = limits();
    zero.max_input_slots = 0;
    let query = encode_query(
        QueryProfile::MapFilterV0_1,
        &empty,
        &empty_set,
        guarantee(&empty_set),
        &identity(),
        zero,
    )
    .unwrap();
    assert_eq!(query.usage().input_slots, 0);
    assert!(
        !query
            .symbols()
            .iter()
            .any(|s| matches!(s.origin(), SymbolOrigin::Input { .. }))
    );
    let mut low_json = limits();
    low_json.ir_json.max_input_bytes = empty.canonical_bytes().len() - 1;
    assert!(matches!(
        encode_query(
            QueryProfile::MapFilterV0_1,
            &empty,
            &empty_set,
            guarantee(&empty_set),
            &identity(),
            low_json
        ),
        Err(QueryError::Json(_))
    ));
}
