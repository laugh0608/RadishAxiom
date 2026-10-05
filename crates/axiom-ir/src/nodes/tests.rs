use super::*;
use crate::declarations::DeclarationErrorKind as InputKind;
use crate::expressions::{TypeErrorKind, UnsupportedTyping};
use crate::json::{JsonErrorKind, ResourceLimit};

#[path = "typing_tests.rs"]
mod typing_tests;

#[path = "flow_tests.rs"]
mod flow_tests;

const TEXT: &str = r#"{"kind":"text"}"#;
const BOOL: &str = r#"{"kind":"bool"}"#;
const INT: &str = r#"{"kind":"int","lower":"0","upper":"10"}"#;
const FIXED: &str = r#"{"kind":"fixed","scale":"2","lower":"0","upper":"10"}"#;

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 16 * 1024 * 1024,
        max_values: 1_000_000,
        max_nesting: 128,
    }
}
fn bytes(value: &Value) -> Vec<u8> {
    let mut result = Vec::new();
    json::encode(value, &mut result);
    result
}
fn parsed(text: &str) -> Value {
    json::parse(text.as_bytes(), limits()).unwrap()
}
fn copy(value: &Value) -> Value {
    json::parse(&bytes(value), limits()).unwrap()
}
fn text(value: &str) -> Value {
    Value::String(value.to_owned())
}
fn object<const N: usize>(members: [(&str, Value); N]) -> Value {
    let mut result: Vec<_> = members
        .into_iter()
        .map(|(key, value)| (key.to_owned(), value, 0))
        .collect();
    result.sort_by(|left, right| left.0.encode_utf16().cmp(right.0.encode_utf16()));
    Value::Object(result)
}
fn at_mut<'a>(mut value: &'a mut Value, path: &[&str]) -> &'a mut Value {
    for key in path {
        value = match value {
            Value::Array(values) => &mut values[key.parse::<usize>().unwrap()],
            Value::Object(members) => {
                &mut members
                    .iter_mut()
                    .find(|(name, _, _)| name == key)
                    .unwrap()
                    .1
            }
            _ => panic!("fixture path"),
        };
    }
    value
}
fn array_mut<'a>(value: &'a mut Value, path: &[&str]) -> &'a mut Vec<Value> {
    let Value::Array(values) = at_mut(value, path) else {
        panic!("fixture array")
    };
    values
}
fn set(value: &mut Value, key: &str, new_value: Value) {
    let Value::Object(members) = value else {
        panic!("fixture object")
    };
    if let Some((_, value, _)) = members.iter_mut().find(|(name, _, _)| name == key) {
        *value = new_value;
    } else {
        members.push((key.to_owned(), new_value, 0));
    }
    members.sort_by(|left, right| left.0.encode_utf16().cmp(right.0.encode_utf16()));
}
fn document() -> Value {
    parsed(
        r#"{"contracts":[],"digest_algorithm":"sha-256","effects":[],"enum_types":[],"format":"axiom-ir","ir_version":"0.1","nodes":[],"outputs":[],"record_types":[],"semantics":{"name":"keyed-finite-table-semantics","sha256":"6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d"},"table_types":[]}"#,
    )
}
// 这里只构造测试输入的声明 ID，不用生产函数生成节点检查期望。
// 声明摘要的独立 oracle 由 tests/normalization.rs 的 Python 向量提供。
fn declaration(doc: &mut Value, collection: &str, domain: &str, definition: Value) -> String {
    let mut hash_input = format!("axiom-ir-v0.1:{domain}\0").into_bytes();
    hash_input.extend(bytes(&definition));
    let id = format!("sha256:{}", radishaxiom_digest::digest_hex(&hash_input));
    let entries = array_mut(doc, &[collection]);
    if !entries.iter().any(|entry| {
        let Value::Object(members) = entry else {
            panic!("fixture entry")
        };
        matches!(decode::member(members, "id"), Value::String(value) if value == &id)
    }) {
        entries.push(object([("id", text(&id)), ("definition", definition)]));
    }
    id
}
fn schema(doc: &mut Value, fields: &[(&str, &str, &str)], keys: &[&str], capacity: &str) -> String {
    let mut fields: Vec<_> = fields.iter().collect();
    fields.sort_by_key(|(name, _, _)| *name);
    let fields = fields
        .into_iter()
        .map(|(name, ty, label)| {
            object([
                ("name", text(name)),
                ("type", parsed(ty)),
                ("label", text(label)),
            ])
        })
        .collect();
    let record = declaration(
        doc,
        "record_types",
        "record-type",
        object([("fields", Value::Array(fields))]),
    );
    declaration(
        doc,
        "table_types",
        "table-type",
        object([
            ("record_type", text(&record)),
            (
                "primary_key",
                Value::Array(keys.iter().map(|key| text(key)).collect()),
            ),
            ("capacity", text(capacity)),
        ]),
    )
}
fn base(capacity: &str) -> (Value, String) {
    let mut doc = document();
    let table = schema(
        &mut doc,
        &[
            ("id", TEXT, "public"),
            ("other", TEXT, "public"),
            ("flag", BOOL, "public"),
            ("units", INT, "public"),
            ("cash", FIXED, "public"),
            ("secret", TEXT, "sensitive"),
            (
                "maybe",
                r#"{"kind":"option","inner":{"kind":"int","lower":"0","upper":"10"}}"#,
                "public",
            ),
        ],
        &["id"],
        capacity,
    );
    input(&mut doc, 0, &table, "source");
    (doc, table)
}
fn node_id(index: usize) -> String {
    format!("sha256:{index:064x}")
}
fn node(doc: &mut Value, index: usize, definition: Value) {
    // 节点 ID 是合成词法值；本切片不声称已核对节点内容身份。
    array_mut(doc, &["nodes"]).push(object([
        ("id", text(&node_id(index))),
        ("definition", definition),
    ]));
}
fn input(doc: &mut Value, index: usize, table: &str, port: &str) {
    node(
        doc,
        index,
        object([
            ("kind", text("input")),
            ("port", text(port)),
            ("table_type", text(table)),
        ]),
    );
}
fn output(doc: &mut Value, name: &str, index: usize) {
    array_mut(doc, &["outputs"]).push(object([
        ("name", text(name)),
        ("node", text(&node_id(index))),
    ]));
}
fn field(slot: &str, name: &str) -> Value {
    object([
        ("op", text("field")),
        ("field", text(name)),
        (
            "record",
            object([("op", text("bound")), ("index", text(slot))]),
        ),
    ])
}
fn projection(name: &str, expression: Value) -> Value {
    object([("name", text(name)), ("expression", expression)])
}
fn filter(doc: &mut Value, index: usize, source: usize, table: &str, predicate: Value) {
    node(
        doc,
        index,
        object([
            ("kind", text("filter")),
            ("source", text(&node_id(source))),
            ("table_type", text(table)),
            ("predicate", predicate),
        ]),
    );
}
fn map(doc: &mut Value, index: usize, source: usize, table: &str, fields: Vec<Value>) {
    node(
        doc,
        index,
        object([
            ("kind", text("map")),
            ("source", text(&node_id(source))),
            ("table_type", text(table)),
            ("fields", Value::Array(fields)),
        ]),
    );
}
fn identity_fields() -> Vec<Value> {
    ["id", "other", "flag", "units", "cash", "secret", "maybe"]
        .iter()
        .map(|name| projection(name, field("0", name)))
        .collect()
}
fn mapped() -> Value {
    let (mut doc, table) = base("4");
    map(&mut doc, 1, 0, &table, identity_fields());
    output(&mut doc, "result", 1);
    doc
}
fn analyze(doc: &Value) -> Result<NodeGraphAnalysis, NodeError> {
    analyze_node_graph(&bytes(doc), limits())
}
fn rejects(doc: &Value, kind: NodeErrorKind, path: &str) {
    assert_eq!(analyze(doc).unwrap_err(), error(kind, path));
}
fn rejects_input(doc: &Value, kind: InputKind, path: &str) {
    assert_eq!(
        analyze(doc).unwrap_err(),
        NodeError::Input(decode::error(kind, path))
    );
}

#[test]
fn all_twelve_candidates_use_the_real_node_entry_including_wrong_algorithms() {
    let cases = [
        ("ax-b01", "correct", 3, 1),
        ("ax-b01", "wrong-add", 3, 1),
        ("ax-b01", "wrong-drop-zero", 3, 1),
        ("ax-b02", "correct", 3, 2),
        ("ax-b02", "wrong-constant-tier", 3, 2),
        ("ax-b02", "wrong-region-join", 3, 2),
        ("ax-b03", "correct", 2, 1),
        ("ax-b03", "wrong-single-group", 3, 1),
        ("ax-b03", "wrong-unit-sum", 3, 1),
        ("ax-b04", "correct", 2, 1),
        ("ax-b04", "wrong-sensitive-filter", 3, 1),
        ("ax-b04", "wrong-sensitive-priority", 2, 1),
    ];
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../benchmarks/keyed-finite-table-v0.1");
    for (task, name, count, inputs) in cases {
        for extension in ["ir.json", "ir.jcs"] {
            let data = std::fs::read(
                root.join(task)
                    .join("candidates")
                    .join(format!("{name}.{extension}")),
            )
            .unwrap();
            let result = analyze_node_graph(&data, limits())
                .unwrap_or_else(|error| panic!("{task}/{name}: {error}"));
            assert_eq!(result.nodes().len(), count);
            assert_eq!(
                result
                    .nodes()
                    .iter()
                    .filter(|node| node.kind() == NodeKind::Input)
                    .count(),
                inputs
            );
            assert_eq!(result.outputs().len(), 1);
            assert_eq!(result.topological_order().len(), count);
            let mut available = BTreeSet::new();
            for &index in result.topological_order() {
                assert!(
                    result.nodes()[index]
                        .predecessors()
                        .iter()
                        .all(|source| available.contains(source))
                );
                assert!(available.insert(index));
            }
        }
    }
}

#[test]
fn permutations_keep_references_and_errors_tied_to_original_array_positions() {
    let mut doc = mapped();
    array_mut(&mut doc, &["nodes"]).reverse();
    array_mut(&mut doc, &["nodes", "0", "definition", "fields"]).reverse();
    let result = analyze(&doc).unwrap();
    assert_eq!(result.topological_order(), &[1, 0]);
    assert_eq!(result.nodes()[0].predecessors(), &[1]);
    assert_eq!(result.nodes()[1].input_port(), Some("source"));
    assert_eq!(
        result.outputs()[0],
        OutputReference {
            name: "result".to_owned(),
            node: 0
        }
    );
    *at_mut(
        &mut doc,
        &["nodes", "0", "definition", "fields", "0", "expression"],
    ) = field("3", "id");
    assert_eq!(
        analyze(&doc).unwrap_err(),
        NodeError::Expression(ExpressionError::Type {
            kind: TypeErrorKind::BoundOutOfRange,
            path: "/nodes/0/definition/fields/0/expression/record/index".to_owned(),
        })
    );
}

#[test]
fn duplicate_ids_ports_outputs_and_missing_interfaces_are_rejected() {
    let mut doc = mapped();
    let duplicate = copy(&array_mut(&mut doc, &["nodes"])[0]);
    array_mut(&mut doc, &["nodes"]).push(duplicate);
    rejects(&doc, NodeErrorKind::DuplicateId, "/nodes/2/id");
    let (mut doc, table) = base("4");
    input(&mut doc, 1, &table, "source");
    output(&mut doc, "out", 0);
    rejects(
        &doc,
        NodeErrorKind::DuplicateName,
        "/nodes/1/definition/port",
    );
    let mut doc = mapped();
    output(&mut doc, "result", 0);
    rejects(&doc, NodeErrorKind::DuplicateName, "/outputs/1/name");
    rejects(&document(), NodeErrorKind::MissingInput, "/nodes");
    let (doc, _) = base("4");
    rejects(&doc, NodeErrorKind::MissingOutput, "/outputs");
}

#[test]
fn dangling_and_wrong_kind_references_are_located() {
    for (path, expected) in [
        (
            vec!["nodes", "1", "definition", "source"],
            "/nodes/1/definition/source",
        ),
        (
            vec!["nodes", "1", "definition", "table_type"],
            "/nodes/1/definition/table_type",
        ),
        (vec!["outputs", "0", "node"], "/outputs/0/node"),
    ] {
        let mut doc = mapped();
        *at_mut(&mut doc, &path) = text(&node_id(999));
        rejects(&doc, NodeErrorKind::UnresolvedReference, expected);
    }
    let mut doc = mapped();
    let table = copy(at_mut(
        &mut doc,
        &["nodes", "0", "definition", "table_type"],
    ));
    *at_mut(&mut doc, &["outputs", "0", "node"]) = table;
    rejects(&doc, NodeErrorKind::UnresolvedReference, "/outputs/0/node");
}

#[test]
fn cycle_diagnostics_identify_cycle_edges_and_dead_nodes_are_not_ignored() {
    let mut doc = mapped();
    *at_mut(&mut doc, &["nodes", "1", "definition", "source"]) = text(&node_id(1));
    rejects(&doc, NodeErrorKind::Cycle, "/nodes/1/definition/source");
    let (mut doc, table) = base("4");
    // 节点 1 是环的下游，错误应定位 2 <-> 3 的真实成环引用。
    for (index, source) in [(1, 2), (2, 3), (3, 2)] {
        filter(&mut doc, index, source, &table, field("0", "flag"));
    }
    output(&mut doc, "result", 1);
    rejects(&doc, NodeErrorKind::Cycle, "/nodes/3/definition/source");
    let mut doc = mapped();
    *at_mut(&mut doc, &["outputs", "0", "node"]) = text(&node_id(0));
    rejects(&doc, NodeErrorKind::DeadNode, "/nodes/1");
    let (mut doc, table) = base("4");
    input(&mut doc, 1, &table, "unused_input");
    output(&mut doc, "result", 0);
    assert!(analyze(&doc).is_ok(), "unused inputs are permitted");
}

#[test]
fn deep_graphs_do_not_use_native_recursion() {
    let (mut doc, table) = base("4");
    for index in 1..=5000 {
        filter(&mut doc, index, index - 1, &table, field("0", "flag"));
    }
    output(&mut doc, "deep", 5000);
    let result = analyze(&doc).unwrap();
    assert_eq!(result.topological_order(), &(0..=5000).collect::<Vec<_>>());
    *at_mut(&mut doc, &["nodes", "1", "definition", "source"]) = text(&node_id(5000));
    rejects(&doc, NodeErrorKind::Cycle, "/nodes/2/definition/source");
}

#[test]
fn closed_members_names_ids_and_tags_are_checked() {
    for path in [
        vec!["nodes", "0"],
        vec!["nodes", "0", "definition"],
        vec!["outputs", "0"],
    ] {
        let mut doc = mapped();
        set(at_mut(&mut doc, &path), "extra", text("ignored?"));
        rejects_input(
            &doc,
            InputKind::UnknownMember,
            &format!("/{}/extra", path.join("/")),
        );
    }
    let mut doc = mapped();
    *at_mut(&mut doc, &["nodes", "1", "definition", "kind"]) = text("read_file");
    rejects(&doc, NodeErrorKind::UnknownKind, "/nodes/1/definition/kind");
    for path in [
        vec!["nodes", "0", "definition", "port"],
        vec!["outputs", "0", "name"],
    ] {
        let mut doc = mapped();
        *at_mut(&mut doc, &path) = text("bad\u{80}");
        rejects_input(
            &doc,
            InputKind::InvalidName,
            &format!("/{}", path.join("/")),
        );
    }
    let mut doc = mapped();
    *at_mut(&mut doc, &["nodes", "1", "definition", "source"]) = text("sha256:bad");
    rejects_input(&doc, InputKind::InvalidId, "/nodes/1/definition/source");
}

#[test]
fn json_budgets_original_offsets_and_partial_success_boundaries_remain_explicit() {
    let mut doc = mapped();
    let data = bytes(&doc);
    for (limit, expected) in [
        (
            JsonLimits {
                max_input_bytes: data.len() - 1,
                ..limits()
            },
            ResourceLimit::InputBytes,
        ),
        (
            JsonLimits {
                max_values: 1,
                ..limits()
            },
            ResourceLimit::Values,
        ),
        (
            JsonLimits {
                max_nesting: 1,
                ..limits()
            },
            ResourceLimit::Nesting,
        ),
    ] {
        assert!(
            matches!(analyze_node_graph(&data, limit).unwrap_err(), NodeError::Input(DeclarationError::Json(error)) if error.kind == JsonErrorKind::ResourceLimit(expected))
        );
    }
    let malformed = b"  {\"nodes\": [null]}";
    assert_eq!(
        analyze_node_graph(malformed, limits()).unwrap_err(),
        NodeError::Input(DeclarationError::Json(crate::json::JsonError {
            kind: JsonErrorKind::NumberOrNull,
            offset: 13,
        }))
    );
    // 契约和节点摘要尚未验收；显式保留这一局部入口的边界。
    *at_mut(&mut doc, &["contracts"]) = Value::Array(vec![Value::Bool(false)]);
    assert!(analyze(&doc).is_ok());
    *at_mut(&mut doc, &["effects"]) = Value::Array(vec![text("io")]);
    rejects_input(&doc, InputKind::NonEmptyEffects, "/effects");
}

#[test]
fn small_graphs_match_an_independent_transitive_closure_oracle() {
    // 穷举三个 filter 的前驱及非空输出子集。oracle 用布尔传递闭包，
    // 不复用生产 Kahn 队列 / 反向遍历，也不按已知候选身份决定期望。
    for a in 0..4 {
        for b in 0..4 {
            for c in 0..4 {
                let sources = [a, b, c];
                let mut reach = [[false; 4]; 4];
                for (index, &source) in sources.iter().enumerate() {
                    reach[source][index + 1] = true;
                }
                for via in 0..4 {
                    for from in 0..4 {
                        for to in 0..4 {
                            reach[from][to] |= reach[from][via] && reach[via][to];
                        }
                    }
                }
                let cycle = (0..4).any(|index| reach[index][index]);
                for output_mask in 1..8 {
                    let (mut doc, table) = base("4");
                    for (index, &source) in sources.iter().enumerate() {
                        filter(&mut doc, index + 1, source, &table, field("0", "flag"));
                    }
                    for index in 1..4 {
                        if output_mask & (1 << (index - 1)) != 0 {
                            output(&mut doc, &format!("out{index}"), index);
                        }
                    }
                    let dead = (1..4).any(|from| {
                        !(1..4).any(|to| {
                            output_mask & (1 << (to - 1)) != 0 && (from == to || reach[from][to])
                        })
                    });
                    let result = analyze(&doc);
                    if cycle {
                        assert!(matches!(
                            result,
                            Err(NodeError::Structure {
                                kind: NodeErrorKind::Cycle,
                                ..
                            })
                        ));
                    } else if dead {
                        assert!(matches!(
                            result,
                            Err(NodeError::Structure {
                                kind: NodeErrorKind::DeadNode,
                                ..
                            })
                        ));
                    } else {
                        assert!(result.is_ok());
                    }
                }
            }
        }
    }
}

#[test]
fn declarations_are_identity_checked_before_node_analysis() {
    let mut doc = mapped();
    *at_mut(
        &mut doc,
        &["record_types", "0", "definition", "fields", "0", "name"],
    ) = text("renamed");
    assert!(
        matches!(analyze(&doc).unwrap_err(), NodeError::Input(DeclarationError::ContentIdMismatch { path, .. }) if path == "/record_types/0/id")
    );
}
