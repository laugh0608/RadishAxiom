use super::*;
use crate::{json::Value, query::SymbolOrigin, replay::*};
fn get<'a>(v: &'a Value, key: &str) -> &'a Value {
    let Value::Object(m) = v else {
        panic!("object")
    };
    &m.iter().find(|(k, _, _)| k == key).unwrap().1
}
fn string(v: &Value) -> &str {
    let Value::String(s) = v else {
        panic!("string")
    };
    s
}
fn text<'a>(v: &'a Value, k: &str) -> &'a str {
    string(get(v, k))
}
fn array(v: &Value) -> &[Value] {
    let Value::Array(a) = v else { panic!("array") };
    a
}
fn replay_limits() -> ReplayLimits {
    ReplayLimits {
        ir_json: limits().query.ir_json,
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
// 仅测试构造：从独立手算 world 的完整类型布局分配所有自由叶；不读取 query 派生项。
fn model_for_world(req: &SolverRequest, world: &[u8], reverse: bool) -> String {
    fn flatten(
        req: &SolverRequest,
        shape: usize,
        value: Option<&Value>,
        atoms: &mut BTreeMap<String, usize>,
        out: &mut Vec<String>,
    ) {
        use super::super::layout::ShapeKind;
        match &req.layout.shapes[shape].kind {
            ShapeKind::Record(_, fields) => {
                for (name, child) in fields {
                    let value = value.map(|v| {
                        get(
                            array(get(v, "fields"))
                                .iter()
                                .find(|f| text(f, "name") == name)
                                .unwrap(),
                            "value",
                        )
                    });
                    flatten(req, *child, value, atoms, out);
                }
            }
            ShapeKind::Option(child) => {
                let some = value.is_some_and(|v| text(v, "kind") == "some");
                out.push(some.to_string());
                flatten(
                    req,
                    *child,
                    value.filter(|_| some).map(|v| get(v, "value")),
                    atoms,
                    out,
                );
            }
            ShapeKind::Bool => out.push(
                value
                    .map(|v| match get(v, "value") {
                        Value::Bool(b) => b.to_string(),
                        _ => panic!("bool"),
                    })
                    .unwrap_or_else(|| "false".into()),
            ),
            ShapeKind::Int(..) | ShapeKind::Fixed(..) => {
                let n = value
                    .map(|v| {
                        text(
                            v,
                            if matches!(&req.layout.shapes[shape].kind, ShapeKind::Fixed(..)) {
                                "coefficient"
                            } else {
                                "value"
                            },
                        )
                    })
                    .unwrap_or("0");
                out.push(
                    n.strip_prefix('-')
                        .map(|n| format!("(- {n})"))
                        .unwrap_or_else(|| n.into()),
                );
            }
            ShapeKind::Enum(_, members) => out.push(
                value
                    .map(|v| members.iter().position(|m| m == text(v, "member")).unwrap())
                    .unwrap_or(0)
                    .to_string(),
            ),
            ShapeKind::Text => {
                let text = value.map(|v| text(v, "value")).unwrap_or("");
                let next = atoms.len();
                let id = *atoms.entry(text.into()).or_insert(next);
                out.push(format!("@Text_{id}"));
            }
        }
    }
    let world = crate::json::parse(world, limits().query.ir_json).unwrap();
    let mut atoms = BTreeMap::new();
    for s in req.query.symbols() {
        if let SymbolOrigin::TextLiteral(v) = s.origin() {
            let id = atoms.len();
            atoms.insert(v.to_string(), id);
        }
    }
    let mut slots = BTreeMap::new();
    for input in &req.layout.inputs {
        let table = array(&world)
            .iter()
            .find(|v| text(v, "interface") == input.interface)
            .unwrap();
        let rows = array(get(table, "rows"));
        for slot in 0..input.capacity {
            let index = if reverse && slot < rows.len() {
                rows.len() - slot - 1
            } else {
                slot
            };
            let row = rows.get(index);
            let mut values = Vec::new();
            flatten(req, input.shape, row, &mut atoms, &mut values);
            slots.insert((input.interface.as_str(), slot), (row.is_some(), values));
        }
    }
    let mut lines = Vec::new();
    for symbol in req.query.symbols() {
        let value = match symbol.origin() {
            SymbolOrigin::TextLiteral(v) => format!("@Text_{}", atoms[v.as_str()]),
            SymbolOrigin::Input {
                interface,
                slot,
                component,
            } => {
                let (active, values) = &slots[&(interface.as_ref(), *slot)];
                component
                    .map(|c| values[c].clone())
                    .unwrap_or_else(|| active.to_string())
            }
        };
        lines.push(format!(
            "(define-fun {} () {} {value})",
            symbol.name(),
            symbol.sort()
        ));
    }
    format!("sat\n(\n{}\n)\n", lines.join("\n"))
}
fn request_for(d: &CanonicalDocument, s: &ObligationSet, id: &str) -> SolverRequest {
    let l = limits();
    let q = encode_query(
        QueryProfile::MapFilterV0_5,
        d,
        s,
        id,
        &generator(),
        l.query.with_compact(super::compact::compact_limits()),
    )
    .unwrap();
    plan_solver_request(
        SolverProfile::Cvc5Query0_3ModelV0_1,
        SolverRequestInput {
            document: d,
            obligations: s,
            obligation_id: id,
            query_profile: QueryProfile::MapFilterV0_5,
            query: &q,
            generator: &generator(),
            tool: &tool(),
        },
        l.with_compact(super::compact::compact_limits()),
    )
    .unwrap()
}
fn replay(
    d: &CanonicalDocument,
    s: &ObligationSet,
    id: &str,
    world: ReplayWorldInput<'_>,
) -> TargetReplayObservation {
    replay_target(
        ReplayProfile::MapFilterV0_1,
        ReplayInput {
            document: d,
            obligations: s,
            obligation_id: id,
            generator: &generator(),
            world,
        },
        replay_limits(),
    )
    .unwrap()
}
#[test]
fn compact_candidates_preserve_full_capacity_pre_and_wrong_replay_distinctions() {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!(
        "radishaxiom-compact-replay-{}-{stamp}",
        std::process::id()
    ));
    std::fs::create_dir(&dir).unwrap();
    let generated = std::process::Command::new("python3")
        .arg(root().join("scripts/generate-p4b-hand-vectors.py"))
        .arg(&dir)
        .output()
        .unwrap();
    assert!(
        generated.status.success(),
        "{}",
        String::from_utf8_lossy(&generated.stderr)
    );
    let names = crate::json::parse(
        &std::fs::read(dir.join("names.jcs")).unwrap(),
        limits().query.ir_json,
    )
    .unwrap();
    let mut count = 0;
    let mut full = false;
    let mut pre = false;
    let mut wrong = std::collections::BTreeSet::new();
    let selected = array(&names)
        .iter()
        .map(string)
        .filter(|n| n.starts_with("ax-b01") || n.starts_with("foreign-key"));
    for name in selected.chain(std::iter::once("ax-b01-full")) {
        let base = if name == "ax-b01-full" {
            "ax-b01-correct"
        } else {
            name
        };
        let path = dir.join(format!("{base}.ir.jcs"));
        let (d, s, _) = setup(path.to_str().unwrap(), limits());
        let mut world = std::fs::read(dir.join(format!("{base}.world.jcs"))).unwrap();
        if name == "ax-b01-full" {
            let mut v = crate::json::parse(&world, limits().query.ir_json).unwrap();
            let Value::Array(tables) = &mut v else {
                panic!("tables")
            };
            let Value::Object(m) = &mut tables[0] else {
                panic!("table")
            };
            let Value::Array(rows) = &mut m.iter_mut().find(|(k, _, _)| k == "rows").unwrap().1
            else {
                panic!("rows")
            };
            let mut first = Vec::new();
            crate::json::encode(&rows[0], &mut first);
            rows.clear();
            for i in 0..100 {
                let mut row = crate::json::parse(&first, limits().query.ir_json).unwrap();
                let Value::Object(m) = &mut row else {
                    panic!("row")
                };
                let Value::Array(fields) =
                    &mut m.iter_mut().find(|(k, _, _)| k == "fields").unwrap().1
                else {
                    panic!("fields")
                };
                let field = fields
                    .iter_mut()
                    .find(|f| text(f, "name") == "order_id")
                    .unwrap();
                let Value::Object(m) = field else {
                    panic!("field")
                };
                let Value::Object(m) = &mut m.iter_mut().find(|(k, _, _)| k == "value").unwrap().1
                else {
                    panic!("value")
                };
                m.iter_mut().find(|(k, _, _)| k == "value").unwrap().1 =
                    Value::String(format!("id{i:03}"));
                rows.push(row);
            }
            world.clear();
            crate::json::encode(&v, &mut world);
        }
        let expected = crate::json::parse(
            &std::fs::read(dir.join(format!("{base}.expected.jcs"))).unwrap(),
            limits().query.ir_json,
        )
        .unwrap();
        for id in array(get(&expected, "targets")).iter().map(string) {
            let req = request_for(&d, &s, id);
            let stdout = model_for_world(&req, &world, true);
            let response =
                parse_solver_response(&req, super::response(&req, stdout.as_bytes())).unwrap();
            let model = response.sat_model().unwrap();
            let candidate = decode_model_world(&req, model).unwrap();
            let observed = replay(
                &d,
                &s,
                id,
                ReplayWorldInput::ModelCandidate {
                    request: &req,
                    model,
                    candidate: &candidate,
                },
            );
            let direct = replay(
                &d,
                &s,
                id,
                ReplayWorldInput::Provided(candidate.world_bytes()),
            );
            assert_eq!(
                observed.result_bytes(),
                direct.result_bytes(),
                "{name} {id}"
            );
            assert_ne!(observed.artifact_digest(), direct.artifact_digest());
            let original = replay(&d, &s, id, ReplayWorldInput::Provided(&world));
            assert_eq!(
                observed.outcome(),
                original.outcome(),
                "{name} {id} hand outcome"
            );
            if name == "ax-b01-full" {
                // AX-B01 规范字段叶序 discount_cents, order_id, state, subtotal_cents。
                let key = |slot| {
                    req.query.symbols().iter().find(|symbol|matches!(symbol.origin(),SymbolOrigin::Input{interface,slot:i,component:Some(1)} if interface.as_ref()=="orders" && *i==slot)).unwrap().name()
                };
                let duplicate = replace_value(&req, &stdout, key(1), key(0));
                let duplicate_response =
                    parse_solver_response(&req, super::response(&req, duplicate.as_bytes()))
                        .unwrap();
                assert!(matches!(
                    decode_model_world(&req, duplicate_response.sat_model().unwrap()),
                    Err(SolverError::InvalidInput {
                        reason: "duplicate-key",
                        ..
                    })
                ));
            }
            if name.contains("full") {
                full = true;
                assert_eq!(
                    array(get(
                        &array(
                            &crate::json::parse(candidate.world_bytes(), limits().query.ir_json)
                                .unwrap()
                        )[0],
                        "rows"
                    ))
                    .len(),
                    100
                );
            }
            if observed.outcome() == ReplayOutcome::PreRejected {
                pre = true;
            }
            if observed.outcome() == ReplayOutcome::TargetViolated {
                wrong.insert(name.to_owned());
            }
            count += 1;
        }
    }
    assert!(full);
    assert!(pre);
    assert!(wrong.iter().any(|n| n.contains("wrong-add")));
    assert!(wrong.iter().any(|n| n.contains("wrong-drop-zero")));
    assert!(count >= 40);
    eprintln!(
        "P4 compact replay {count} hand results matched direct IR world; full 100, Pre and both wrong covered"
    );
    std::fs::remove_dir_all(dir).unwrap();
}
#[test]
fn compact_composite_models_keep_text_order_and_all_origins() {
    let l = limits();
    let (d, s, q) = setup("contracts/solver-model-v0.1/inputs/composite.jcs", l);
    let old = plan(&d, &s, &q, l).unwrap();
    let new = request_for(&d, &s, q.binding().obligation());
    let child=std::process::Command::new("python3").arg("-c").arg("import json,sys; d=json.load(open(sys.argv[1])); syms=json.load(sys.stdin)['symbols']; out=['sat','('];\nfor s in syms:\n o=s['origin']; v=d['literal_atoms'][o['value']] if o['kind']=='text-literal' else (str(d['slots'][o['interface']][int(o['slot'])]['active']).lower() if o['component']=='active' else d['slots'][o['interface']][int(o['slot'])]['values'][int(o['component'])]); out.append('(define-fun '+s['name']+' () '+s['sort']+' '+v+')')\nout.append(')'); print('\\n'.join(out))").arg(root().join("contracts/solver-model-v0.1/hand-cases.json")).stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).spawn().and_then(|mut child|{use std::io::Write;child.stdin.take().unwrap().write_all(old.symbol_bytes())?;child.wait_with_output()}).unwrap();
    assert!(child.status.success());
    let old_stdout = String::from_utf8(child.stdout).unwrap();
    let mut new_lines = Vec::new();
    for line in old_stdout.lines().filter(|l| l.starts_with("(define-fun ")) {
        let old_name = line.split_ascii_whitespace().nth(1).unwrap();
        let original = old
            .query
            .symbols()
            .iter()
            .find(|s| s.name() == old_name)
            .unwrap();
        let new_name = new
            .query
            .symbols()
            .iter()
            .find(|s| s.origin() == original.origin())
            .unwrap()
            .name();
        new_lines.push(line.replacen(old_name, new_name, 1));
    }
    new_lines.reverse();
    let new_stdout = format!("sat\n(\n{}\n)\n", new_lines.join("\n")).replace("@Text_", "@Text_7");
    let a = parse_solver_response(&old, response(&old, old_stdout.as_bytes())).unwrap();
    let a = decode_model_world(&old, a.sat_model().unwrap()).unwrap();
    let b = parse_solver_response(&new, response(&new, new_stdout.as_bytes())).unwrap();
    let b = decode_model_world(&new, b.sat_model().unwrap()).unwrap();
    assert_eq!(a.world_bytes(), b.world_bytes());
    assert_ne!(a.text_class_bytes(), b.text_class_bytes());
    let c = parse_solver_response(
        &new,
        response(&new, new_stdout.replace("@Text_7", "@Text_9").as_bytes()),
    )
    .unwrap();
    let c = decode_model_world(&new, c.sat_model().unwrap()).unwrap();
    assert_eq!(b.world_bytes(), c.world_bytes());
    assert_eq!(b.text_class_bytes(), c.text_class_bytes());
}
