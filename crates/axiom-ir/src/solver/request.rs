use super::{
    encoding::{self, obj, s, strings},
    layout::InputLayout,
    *,
};
use crate::{
    json::Value,
    obligations::raw_digest,
    query::{SymbolOrigin, check_query},
};

fn limit_value(l: SolverLimits) -> Value {
    let mut component = vec![
        ("request_bytes", s(l.request_bytes.to_string())),
        ("response_bytes", s(l.response_bytes.to_string())),
        ("symbol_bytes", s(l.symbol_bytes.to_string())),
        ("layout_bytes", s(l.layout_bytes.to_string())),
        ("tokens", s(l.tokens.to_string())),
        ("token_bytes", s(l.token_bytes.to_string())),
        ("syntax_nodes", s(l.syntax_nodes.to_string())),
        ("syntax_depth", s(l.syntax_depth.to_string())),
        ("integer_digits", s(l.integer_digits.to_string())),
        ("definitions", s(l.definitions.to_string())),
        ("alias_edges", s(l.alias_edges.to_string())),
        ("layout_items", s(l.layout_items.to_string())),
        ("input_slots", s(l.input_slots.to_string())),
        ("value_cells", s(l.value_cells.to_string())),
        ("decode_steps", s(l.decode_steps.to_string())),
        ("text_bytes", s(l.text_bytes.to_string())),
        ("world_bytes", s(l.world_bytes.to_string())),
        ("candidate_bytes", s(l.candidate_bytes.to_string())),
    ];
    let q = l.query;
    component.push((
        "query",
        obj(vec![
            (
                "ir_json",
                obj(vec![
                    ("max_input_bytes", s(q.ir_json.max_input_bytes.to_string())),
                    ("max_values", s(q.ir_json.max_values.to_string())),
                    ("max_nesting", s(q.ir_json.max_nesting.to_string())),
                ]),
            ),
            ("max_input_slots", s(q.max_input_slots.to_string())),
            ("max_value_cells", s(q.max_value_cells.to_string())),
            (
                "max_expression_instances",
                s(q.max_expression_instances.to_string()),
            ),
            (
                "max_slot_comparisons",
                s(q.max_slot_comparisons.to_string()),
            ),
            ("max_smt_nodes", s(q.max_smt_nodes.to_string())),
            ("max_output_bytes", s(q.max_output_bytes.to_string())),
        ]),
    ));
    obj(vec![
        ("component", obj(component)),
        (
            "tool_internal",
            obj(vec![
                ("semantic_steps", s("1000000")),
                ("wall_clock_ms", s("5000")),
            ]),
        ),
        (
            "process_outer",
            obj(vec![
                ("stdin_bytes", s("1048576")),
                ("stdout_bytes", s("4194304")),
                ("stderr_bytes", s("65536")),
                ("wall_clock_ms", s("6000")),
                ("working_memory_bytes", s("134217728")),
            ]),
        ),
    ])
}
fn arguments() -> Value {
    strings([
        "--safe-mode=safe",
        "--strict-parsing",
        "--force-logic=QF_UFLIA",
        "--lang=smt2",
        "--no-incremental",
        "--produce-models",
        "--dump-models",
        "--check-models",
        "--produce-proofs",
        "--check-proofs",
        "--rlimit-per=1000000",
        "--tlimit-per=5000",
    ])
}

pub(super) fn plan(
    profile: SolverProfile,
    input: SolverRequestInput<'_>,
    limits: SolverLimits,
) -> Result<SolverRequest> {
    let mut b = Budget::new(limits, SolverStage::Request);
    b.charge(SolverResource::StdinBytes, input.query.bytes().len())?;
    let query = check_query(
        input.query_profile,
        input.query.bytes(),
        input.document,
        input.obligations,
        input.obligation_id,
        input.generator,
        limits.query,
    )
    .map_err(SolverError::Query)?;
    if query.binding() != input.query.binding()
        || query.symbols() != input.query.symbols()
        || query.artifact_digest() != input.query.artifact_digest()
    {
        return Err(SolverError::BindingMismatch);
    }
    let layout = InputLayout::build(input.document, query.symbols(), &mut b)?;
    let layout_bytes = encoding::output(&mut b, SolverResource::LayoutBytes, |out| {
        layout.emit(
            query.binding().ir_artifact(),
            query.artifact_digest(),
            &mut |v| out(v),
        )
    })?;
    let mut catalogue = BTreeMap::new();
    let mut symbols = Vec::new();
    b.charge(SolverResource::LayoutItems, query.symbols().len())?;
    let mut ordered: Vec<_> = query.symbols().iter().collect();
    ordered.sort_by(|a, c| a.name().cmp(c.name()));
    for symbol in ordered {
        catalogue.insert(b.copy(symbol.name())?, Sort::parse(symbol.sort())?);
        let origin = match symbol.origin() {
            SymbolOrigin::TextLiteral(v) => {
                obj(vec![("kind", s("text-literal")), ("value", s(b.copy(v)?))])
            }
            SymbolOrigin::Input {
                interface,
                slot,
                component,
            } => obj(vec![
                ("kind", s("input")),
                ("interface", s(b.copy(interface)?)),
                ("slot", s(slot.to_string())),
                (
                    "component",
                    s(component
                        .map(|n| n.to_string())
                        .unwrap_or_else(|| "active".to_owned())),
                ),
            ]),
        };
        symbols.push(obj(vec![
            ("name", s(b.copy(symbol.name())?)),
            ("sort", s(symbol.sort())),
            ("origin", origin),
        ]));
    }
    let mut derived = BTreeMap::new();
    // 这里只读生产 strict 重建的精确 query，不是接受任意 SMT 的第二入口。
    for line in std::str::from_utf8(query.bytes())
        .map_err(|_| SolverError::Internal("query UTF-8"))?
        .lines()
    {
        if let Some(rest) = line.strip_prefix("(define-fun ") {
            b.charge(SolverResource::LayoutItems, 1)?;
            let mut tokens = rest.split_ascii_whitespace();
            let name = tokens
                .next()
                .ok_or(SolverError::Internal("query definition"))?;
            if tokens.next() != Some("()") {
                return Err(SolverError::Internal("query arity"));
            }
            let sort = Sort::parse(tokens.next().ok_or(SolverError::Internal("query sort"))?)?;
            if catalogue.insert(b.copy(name)?, sort).is_some() {
                return Err(SolverError::Internal("query duplicate name"));
            }
            derived.insert(b.copy(name)?, sort);
        }
    }
    let derived = derived
        .into_iter()
        .map(|(name, sort)| obj(vec![("name", s(name)), ("sort", s(sort.name()))]))
        .collect();
    let symbols = obj(vec![
        ("format", s("axiom-p4-query-symbols")),
        ("version", s("0.1")),
        ("query_raw_digest", s(query.artifact_digest())),
        ("symbols", Value::Array(symbols)),
        ("derived", Value::Array(derived)),
    ]);
    let symbol_bytes = encoding::canonical(&symbols, SolverResource::SymbolBytes, &mut b)?;
    let binding = query.binding();
    let value = obj(vec![
        ("format", s("axiom-p4-solver-request")),
        ("version", s("0.1")),
        ("profile", s(profile.as_str())),
        ("protocol_rules", s(raw_digest(RULES))),
        (
            "query",
            obj(vec![
                ("artifact_type", s(binding.artifact_type())),
                ("dialect", s(binding.solver_dialect())),
                ("encoding_profile", s(binding.encoding_profile())),
                ("raw_digest", s(query.artifact_digest())),
                ("byte_length", s(query.bytes().len().to_string())),
            ]),
        ),
        (
            "binding",
            obj(vec![
                ("ir_artifact", s(binding.ir_artifact())),
                ("ir_document_digest", s(binding.ir_document_digest())),
                (
                    "obligation_set_artifact",
                    s(binding.obligation_set_artifact()),
                ),
                ("obligation", s(binding.obligation())),
                ("semantics_digest", s(binding.semantics_digest())),
                ("generator_source", s(binding.generator().source_digest())),
            ]),
        ),
        ("symbols", s(raw_digest(&symbol_bytes))),
        ("layout", s(raw_digest(&layout_bytes))),
        (
            "tool",
            obj(vec![
                ("name", s("cvc5-cli")),
                ("version", s("1.3.4")),
                ("platform", s(&input.tool.platform)),
                ("payload_digest", s(&input.tool.payload)),
                ("acceptance_record_digest", s(&input.tool.acceptance)),
            ]),
        ),
        (
            "adapter",
            obj(vec![
                ("status", s("planned-not-calibrated")),
                ("base_execution_profile", s("cvc5-1.3.4-qf-uflia-v0.1")),
                ("base_execution_profile_digest", s(raw_digest(BASE))),
                ("argument_tokens", arguments()),
                ("stdin", s("query-bytes-then-eof")),
            ]),
        ),
        ("limits", limit_value(limits)),
    ]);
    let bytes = encoding::canonical(&value, SolverResource::RequestBytes, &mut b)?;
    let raw_digest = raw_digest(&bytes);
    Ok(SolverRequest {
        bytes,
        raw_digest,
        symbol_bytes,
        layout_bytes,
        query,
        layout,
        catalogue,
        limits,
        usage: b.usage,
    })
}
