use super::{
    engine::{Cause, Context, Detail, Engine, Location, Observation, Val},
    flat::Node,
    *,
};
use std::collections::BTreeMap;

fn quoted(s: &str) -> usize {
    let mut n = 0;
    json::emit_string(s, &mut |v| n += v.len());
    n
}
pub(super) fn location_size(
    e: &Engine<'_>,
    anchor: &str,
    path: &[String],
    context: &[Context<'_>],
) -> usize {
    let mut n = b"{\"anchor\":,\"context\":[],\"path\":[]}".len()
        + quoted(anchor)
        + path.len().saturating_sub(1)
        + context.len().saturating_sub(1);
    for p in path {
        n += quoted(p);
    }
    for c in context {
        n += b"{\"key\":[],\"node\":}".len() + quoted(c.node) + c.key.len().saturating_sub(1);
        for &k in &c.key {
            n += match &e.values[k] {
                Val::Bool(v) => b"{\"kind\":\"bool\",\"value\":}".len() + if *v { 4 } else { 5 },
                Val::Int(v) => b"{\"kind\":\"int\",\"value\":}".len() + quoted(v.as_str()),
                Val::Fixed(s, v) => {
                    b"{\"coefficient\":,\"kind\":\"fixed\",\"scale\":}".len()
                        + quoted(s)
                        + quoted(v.as_str())
                }
                Val::Text(v) => b"{\"kind\":\"text\",\"value\":}".len() + quoted(v),
                Val::Enum(t, i) => {
                    b"{\"enum_type\":,\"kind\":\"enum\",\"member\":}".len()
                        + quoted(t)
                        + quoted(&e.enums[t].members[*i])
                }
                _ => unreachable!("scalar key"),
            };
        }
    }
    n
}
impl Engine<'_> {
    fn value_json(&self, id: usize, j: &mut Json, b: &mut Budget) -> Result<usize> {
        let fields = match &self.values[id] {
            Val::Bool(v) => vec![("kind", j.s("bool", b)?), ("value", j.boolean(*v, b)?)],
            Val::Int(n) => vec![("kind", j.s("int", b)?), ("value", j.s(n.as_str(), b)?)],
            Val::Fixed(s, n) => vec![
                ("kind", j.s("fixed", b)?),
                ("coefficient", j.s(n.as_str(), b)?),
                ("scale", j.s(s, b)?),
            ],
            Val::Text(s) => {
                b.charge(ReplayResource::TextBytes, s.len())?;
                vec![("kind", j.s("text", b)?), ("value", j.s(s, b)?)]
            }
            Val::Enum(t, i) => vec![
                ("kind", j.s("enum", b)?),
                ("enum_type", j.s(t, b)?),
                ("member", j.s(&self.enums[t].members[*i], b)?),
            ],
            _ => return Err(ReplayError::Internal("scalar witness")),
        };
        j.obj(fields, b)
    }
    fn values_json(&self, ids: &[usize], j: &mut Json, b: &mut Budget) -> Result<usize> {
        b.charge(ReplayResource::ValueCells, ids.len())?;
        let ids = ids
            .iter()
            .map(|&id| self.value_json(id, j, b))
            .collect::<Result<Vec<_>>>()?;
        j.arr(ids, b)
    }
    fn location_json(&self, id: usize, j: &mut Json, b: &mut Budget) -> Result<usize> {
        let Location {
            anchor,
            path,
            context,
        } = &self.locations[id];
        let mut contexts = Vec::new();
        b.charge(ReplayResource::ValueCells, context.len())?;
        for c in context {
            let key = self.values_json(&c.key, j, b)?;
            let node = j.s(c.node, b)?;
            contexts.push(j.obj(vec![("node", node), ("key", key)], b)?);
        }
        let context = j.arr(contexts, b)?;
        let path = strings(path, j, b)?;
        let anchor = j.s(anchor, b)?;
        j.obj(
            vec![("anchor", anchor), ("path", path), ("context", context)],
            b,
        )
    }
    fn cause_json(&self, mut id: usize, j: &mut Json, b: &mut Budget) -> Result<usize> {
        let mut chain = Vec::new();
        let mut result = loop {
            b.step()?;
            match &self.causes[id] {
                Cause::Dependency {
                    node,
                    source,
                    cause,
                } => {
                    b.charge(ReplayResource::ValueCells, 1)?;
                    chain.push((*node, *source));
                    id = *cause;
                }
                Cause::Range(location) => {
                    let kind = j.s("range", b)?;
                    let location = self.location_json(*location, j, b)?;
                    break j.obj(vec![("kind", kind), ("location", location)], b)?;
                }
                Cause::Capacity {
                    node,
                    actual,
                    capacity,
                } => {
                    let k = j.s("capacity", b)?;
                    let n = j.s(node, b)?;
                    let a = j.n(*actual, b)?;
                    let c = j.s(capacity, b)?;
                    break j.obj(
                        vec![
                            ("kind", k),
                            ("node", n),
                            ("actual_rows", a),
                            ("declared_capacity", c),
                        ],
                        b,
                    )?;
                }
            }
        };
        for (node, source) in chain.into_iter().rev() {
            b.step()?;
            let kind = j.s("dependency", b)?;
            let node = j.s(node, b)?;
            let source = j.s(source, b)?;
            result = j.obj(
                vec![
                    ("kind", kind),
                    ("node", node),
                    ("source", source),
                    ("cause", result),
                ],
                b,
            )?;
        }
        Ok(result)
    }
    pub(super) fn result_json(
        &self,
        result: &Observation<'_>,
        j: &mut Json,
        b: &mut Budget,
    ) -> Result<usize> {
        let fields = match result {
            Observation::Input {
                interface,
                rows,
                path,
                reason,
            } => vec![
                ("kind", j.s("input-rejected", b)?),
                ("interface", j.s(interface, b)?),
                ("rows", numbers(rows, j, b)?),
                ("path", strings(path, j, b)?),
                ("reason", j.s(reason, b)?),
            ],
            Observation::Pre {
                contract,
                reason,
                location,
            } => vec![
                ("kind", j.s("pre-rejected", b)?),
                ("contract", j.s(contract, b)?),
                ("reason", j.s(reason, b)?),
                ("location", self.location_json(*location, j, b)?),
            ],
            Observation::Holds { detail } | Observation::Violated { detail } => {
                let violated = matches!(result, Observation::Violated { .. });
                let detail = self.detail_json(detail, j, b)?;
                vec![
                    (
                        "kind",
                        j.s(
                            if violated {
                                "target-violated"
                            } else {
                                "target-not-violated"
                            },
                            b,
                        )?,
                    ),
                    (if violated { "witness" } else { "observation" }, detail),
                ]
            }
        };
        j.obj(fields, b)
    }
    fn detail_json(&self, d: &Detail<'_>, j: &mut Json, b: &mut Budget) -> Result<usize> {
        let mut f = Vec::new();
        match d {
            Detail::RangeHolds => {
                f.push(("kind", j.s("numeric-range", b)?));
                f.push(("instances", j.n(self.instances, b)?));
            }
            Detail::RangeViolation => {
                let r = self.range.as_ref().expect("range witness");
                let Value::Object(fields) = r.ty else {
                    unreachable!()
                };
                b.charge(ReplayResource::ValueCells, fields.len())?;
                let type_fields = fields
                    .iter()
                    .map(|(k, v, _)| Ok((k.as_str(), j.s(string(v), b)?)))
                    .collect::<Result<Vec<_>>>()?;
                let ty = j.obj(type_fields, b)?;
                f.extend([
                    ("kind", j.s("numeric-range", b)?),
                    ("location", self.location_json(r.location, j, b)?),
                    ("operands", self.values_json(&r.operands, j, b)?),
                    ("mathematical_value", self.value_json(r.value, j, b)?),
                    ("result_type", ty),
                ]);
            }
            Detail::Totality { node, cause } => {
                f.extend([("kind", j.s("totality", b)?), ("node", j.s(node, b)?)]);
                if let Some(c) = cause {
                    f.push(("cause", self.cause_json(*c, j, b)?));
                } else {
                    f.push(("ok", j.boolean(true, b)?));
                }
            }
            Detail::Cardinality {
                node,
                ready,
                cause,
                reason,
                rows,
                key,
                actual,
                capacity,
            } => {
                f.extend([
                    ("kind", j.s("key-cardinality", b)?),
                    ("node", j.s(node, b)?),
                ]);
                if !ready {
                    f.push(("ready", j.boolean(false, b)?));
                    f.push(("cause", self.cause_json(cause.expect("not ready"), j, b)?));
                } else if let Some(reason) = reason {
                    f.push(("reason", j.s(reason, b)?));
                    if *reason == "capacity" {
                        f.extend([
                            ("actual_rows", j.n(*actual, b)?),
                            ("declared_capacity", j.s(capacity, b)?),
                        ]);
                    } else {
                        f.extend([
                            ("rows", numbers(rows, j, b)?),
                            ("key", self.values_json(key, j, b)?),
                        ]);
                    }
                } else {
                    f.extend([
                        ("ready", j.boolean(true, b)?),
                        ("unique", j.boolean(true, b)?),
                        ("capacity", j.boolean(true, b)?),
                    ]);
                }
            }
            Detail::Coverage {
                node,
                ready,
                cause,
                direction,
                key,
                matches,
            } => {
                f.extend([("kind", j.s("row-coverage", b)?), ("node", j.s(node, b)?)]);
                if !ready {
                    f.extend([
                        ("ready", j.boolean(false, b)?),
                        ("cause", self.cause_json(cause.expect("not ready"), j, b)?),
                    ]);
                } else if let Some(d) = direction {
                    f.extend([
                        ("direction", j.s(d, b)?),
                        ("key", self.values_json(key, j, b)?),
                        ("matches", j.n(*matches, b)?),
                    ]);
                } else {
                    f.extend([
                        ("ready", j.boolean(true, b)?),
                        ("forward", j.boolean(true, b)?),
                        ("backward", j.boolean(true, b)?),
                    ]);
                }
            }
            Detail::Guarantee {
                contract,
                reason,
                cause,
                location,
            } => {
                f.extend([
                    ("kind", j.s("contract-guarantee", b)?),
                    ("contract", j.s(contract, b)?),
                ]);
                if let Some(r) = reason {
                    let c = if let Some(c) = cause {
                        self.cause_json(*c, j, b)?
                    } else {
                        self.location_json(location.expect("formula location"), j, b)?
                    };
                    f.extend([("reason", j.s(r, b)?), ("cause", c)]);
                } else {
                    f.extend([
                        ("program_ok", j.boolean(true, b)?),
                        ("formula_ok", j.boolean(true, b)?),
                        ("value", j.boolean(true, b)?),
                    ]);
                }
            }
        }
        j.obj(f, b)
    }
}
fn strings(s: &[String], j: &mut Json, b: &mut Budget) -> Result<usize> {
    b.charge(ReplayResource::ValueCells, s.len())?;
    let v = s.iter().map(|s| j.s(s, b)).collect::<Result<Vec<_>>>()?;
    j.arr(v, b)
}
fn numbers(s: &[usize], j: &mut Json, b: &mut Budget) -> Result<usize> {
    b.charge(ReplayResource::ValueCells, s.len())?;
    let v = s.iter().map(|&s| j.n(s, b)).collect::<Result<Vec<_>>>()?;
    j.arr(v, b)
}

pub(super) fn finish(
    mut j: Json,
    result: usize,
    outcome: ReplayOutcome,
    binding: usize,
    source: usize,
    world: &str,
    b: &mut Budget,
) -> Result<TargetReplayObservation> {
    let mut limit_fields = Vec::new();
    let mut usage_fields = Vec::new();
    let mut slots = BTreeMap::new();
    macro_rules! field {
        ($name:ident) => {{
            let name = stringify!($name);
            let l = j.n(b.limits.$name, b)?;
            let u = j.n(0, b)?;
            limit_fields.push((name, l));
            usage_fields.push((name, u));
            slots.insert(name, u);
        }};
    }
    field!(world_bytes);
    field!(world_nodes);
    field!(world_depth);
    field!(type_items);
    field!(rows);
    field!(value_cells);
    field!(evaluation_steps);
    field!(comparisons);
    field!(integer_digits);
    field!(digit_work);
    field!(text_bytes);
    field!(path_bytes);
    field!(output_bytes);
    let ir = b.limits.ir_json;
    let ir_fields = vec![
        ("max_input_bytes", j.n(ir.max_input_bytes, b)?),
        ("max_values", j.n(ir.max_values, b)?),
        ("max_nesting", j.n(ir.max_nesting, b)?),
    ];
    let ir = j.obj(ir_fields, b)?;
    limit_fields.push(("ir_json", ir));
    let limits = j.obj(limit_fields, b)?;
    let usage = j.obj(usage_fields, b)?;
    let fields = vec![
        ("format", j.s(REPLAY_ARTIFACT, b)?),
        ("version", j.s("0.1", b)?),
        ("profile", j.s(REPLAY_PROFILE, b)?),
        ("rule_digest", j.s(&raw_digest(RULE), b)?),
        ("binding", binding),
        ("source", source),
        ("world_raw_digest", j.s(world, b)?),
        ("limits", limits),
        ("result", result),
        ("usage", usage),
    ];
    let root = j.obj(fields, b)?;
    let tape = j.tape(root, b)?;
    let result_tape = j.tape(result, b)?;
    // 两次实际 token 遍历（计数和写入）先收费，计数器使用固定容量缓冲区。
    let steps = tape
        .len()
        .checked_add(result_tape.len())
        .and_then(|n| n.checked_mul(2))
        .ok_or_else(|| b.error(ReplayResource::EvaluationSteps))?;
    b.charge(ReplayResource::EvaluationSteps, steps)?;
    let capacity = usize::MAX.to_string().len();
    b.charge(
        ReplayResource::ValueCells,
        slots
            .len()
            .checked_mul(capacity)
            .ok_or_else(|| b.error(ReplayResource::ValueCells))?,
    )?;
    for &id in slots.values() {
        j.nodes[id] = Node::String(String::with_capacity(capacity));
    }
    fn put(j: &mut Json, id: usize, n: usize) -> (usize, usize) {
        use std::fmt::Write;
        let Node::String(s) = &mut j.nodes[id] else {
            unreachable!()
        };
        let old = s.len();
        s.clear();
        write!(s, "{n}").expect("String write");
        (old, s.len())
    }
    macro_rules! set {
        ($name:ident) => {
            put(&mut j, slots[stringify!($name)], b.usage.$name);
        };
    }
    set!(world_bytes);
    set!(world_nodes);
    set!(world_depth);
    set!(type_items);
    set!(rows);
    set!(value_cells);
    set!(evaluation_steps);
    set!(comparisons);
    set!(integer_digits);
    set!(digit_work);
    set!(text_bytes);
    set!(path_bytes);
    set!(output_bytes);
    let mut length = j.tape_length(&tape)?;
    loop {
        b.step()?;
        let (old, new) = put(&mut j, slots["evaluation_steps"], b.usage.evaluation_steps);
        length = length
            .checked_sub(old)
            .and_then(|v| v.checked_add(new))
            .ok_or_else(|| b.error(ReplayResource::OutputBytes))?;
        let (old, new) = put(&mut j, slots["output_bytes"], length);
        let next = length
            .checked_sub(old)
            .and_then(|v| v.checked_add(new))
            .ok_or_else(|| b.error(ReplayResource::OutputBytes))?;
        if next == length {
            break;
        }
        length = next;
    }
    b.observe(ReplayResource::OutputBytes, length)?;
    let result_length = j.tape_length(&result_tape)?;
    let bytes = j.encode_tape(&tape, length);
    let result = j.encode_tape(&result_tape, result_length);
    debug_assert_eq!(bytes.len(), length);
    let digest = raw_digest(&bytes);
    Ok(TargetReplayObservation {
        bytes,
        result,
        digest,
        usage: b.usage.clone(),
        outcome,
    })
}
