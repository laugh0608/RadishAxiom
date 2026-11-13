use super::*;
use crate::{
    query::{CompactQueryLimits, QueryLimits},
    solver::SolverLimits,
};

fn number(row: &Members, key: &'static str, maximum: usize) -> Result<usize> {
    let value = decimal(text(row, key)?, key)?;
    if value > maximum {
        return Err(ReviewError::Limit(key));
    }
    Ok(value)
}

fn json_limits(value: &Value, cap: JsonLimits) -> Result<JsonLimits> {
    let row = shape(
        value,
        "json limits",
        &["max_input_bytes", "max_values", "max_nesting"],
    )?;
    Ok(JsonLimits {
        max_input_bytes: number(row, "max_input_bytes", cap.max_input_bytes)?,
        max_values: number(row, "max_values", cap.max_values)?,
        max_nesting: number(row, "max_nesting", cap.max_nesting)?,
    })
}

pub(super) fn solver(value: &Value, cap: SolverBudgets) -> Result<SolverBudgets> {
    let row = shape(
        value,
        "request component budgets",
        &[
            "query",
            "request_bytes",
            "response_bytes",
            "symbol_bytes",
            "layout_bytes",
            "tokens",
            "token_bytes",
            "syntax_nodes",
            "syntax_depth",
            "integer_digits",
            "definitions",
            "alias_edges",
            "layout_items",
            "input_slots",
            "value_cells",
            "decode_steps",
            "text_bytes",
            "world_bytes",
            "candidate_bytes",
        ],
    )?;
    let query = shape(member(row, "query"), "query budgets", &["base", "compact"])?;
    let base = shape(
        member(query, "base"),
        "query base budgets",
        &[
            "ir_json",
            "max_input_slots",
            "max_value_cells",
            "max_expression_instances",
            "max_slot_comparisons",
            "max_smt_nodes",
            "max_output_bytes",
        ],
    )?;
    let q = cap.base.query;
    let query_limits = QueryLimits {
        ir_json: json_limits(member(base, "ir_json"), q.ir_json)?,
        max_input_slots: number(base, "max_input_slots", q.max_input_slots)?,
        max_value_cells: number(base, "max_value_cells", q.max_value_cells)?,
        max_expression_instances: number(
            base,
            "max_expression_instances",
            q.max_expression_instances,
        )?,
        max_slot_comparisons: number(base, "max_slot_comparisons", q.max_slot_comparisons)?,
        max_smt_nodes: number(base, "max_smt_nodes", q.max_smt_nodes)?,
        max_output_bytes: number(base, "max_output_bytes", q.max_output_bytes)?,
    };
    let compact = shape(
        member(query, "compact"),
        "compact budgets",
        &[
            "max_normalized_nodes",
            "max_normalized_edges",
            "max_scratch_cells",
            "max_work_steps",
            "max_temporary_bytes",
            "max_integer_digits",
            "max_dag_depth",
        ],
    )?;
    let c = cap
        .compact
        .ok_or(invalid("backend limits", "explicit compact cap required"))?;
    let compact = CompactQueryLimits {
        max_normalized_nodes: number(compact, "max_normalized_nodes", c.max_normalized_nodes)?,
        max_normalized_edges: number(compact, "max_normalized_edges", c.max_normalized_edges)?,
        max_scratch_cells: number(compact, "max_scratch_cells", c.max_scratch_cells)?,
        max_work_steps: number(compact, "max_work_steps", c.max_work_steps)?,
        max_temporary_bytes: number(compact, "max_temporary_bytes", c.max_temporary_bytes)?,
        max_integer_digits: number(compact, "max_integer_digits", c.max_integer_digits)?,
        max_dag_depth: number(compact, "max_dag_depth", c.max_dag_depth)?,
    };
    let cap = cap.base;
    macro_rules! n {
        ($field:ident) => {
            number(row, stringify!($field), cap.$field)?
        };
    }
    Ok(SolverLimits {
        query: query_limits,
        request_bytes: n!(request_bytes),
        response_bytes: n!(response_bytes),
        symbol_bytes: n!(symbol_bytes),
        layout_bytes: n!(layout_bytes),
        tokens: n!(tokens),
        token_bytes: n!(token_bytes),
        syntax_nodes: n!(syntax_nodes),
        syntax_depth: n!(syntax_depth),
        integer_digits: n!(integer_digits),
        definitions: n!(definitions),
        alias_edges: n!(alias_edges),
        layout_items: n!(layout_items),
        input_slots: n!(input_slots),
        value_cells: n!(value_cells),
        decode_steps: n!(decode_steps),
        text_bytes: n!(text_bytes),
        world_bytes: n!(world_bytes),
        candidate_bytes: n!(candidate_bytes),
    }
    .with_compact(compact))
}

fn values<'a>(run: &Execution<'a>) -> Result<BTreeMap<(&'a str, &'a str), usize>> {
    match run.limits {
        execution::ExecutionLimits::Backend(values) => execution::limit_values(values),
        _ => Err(invalid("backend limits", "mode")),
    }
}

pub(super) fn solve(run: &Execution<'_>) -> Result<()> {
    let actual = values(run)?;
    let expected = BTreeMap::from([
        (("internal-semantic-steps", "step"), 1_000_000),
        (("internal-wall-clock", "millisecond"), 5_000),
        (("outer-stderr", "byte"), 65_536),
        (("outer-stdin", "byte"), 1_048_576),
        (("outer-stdout", "byte"), 4_194_304),
        (("outer-wall-clock", "millisecond"), 6_000),
        (("outer-working-memory", "byte"), 134_217_728),
    ]);
    if actual != expected {
        return Err(invalid("backend limits", "process limits"));
    }
    Ok(())
}

pub(super) fn replay(run: &Execution<'_>, cap: ReplayLimits) -> Result<ReplayLimits> {
    let mut values = values(run)?;
    let mut take = |name: &'static str, unit, maximum| {
        let value = values
            .remove(&(name, unit))
            .ok_or(invalid("backend limits", "missing name or unit"))?;
        if value > maximum {
            return Err(ReviewError::Limit(name));
        }
        Ok(value)
    };
    let result = ReplayLimits {
        ir_json: JsonLimits {
            max_input_bytes: take("ir-input-bytes", "byte", cap.ir_json.max_input_bytes)?,
            max_nesting: take("ir-nesting", "level", cap.ir_json.max_nesting)?,
            max_values: take("ir-values", "value", cap.ir_json.max_values)?,
        },
        world_bytes: take("world-bytes", "byte", cap.world_bytes)?,
        world_nodes: take("world-nodes", "node", cap.world_nodes)?,
        world_depth: take("world-depth", "level", cap.world_depth)?,
        type_items: take("type-items", "item", cap.type_items)?,
        rows: take("rows", "row", cap.rows)?,
        value_cells: take("value-cells", "cell", cap.value_cells)?,
        evaluation_steps: take("evaluation-steps", "step", cap.evaluation_steps)?,
        comparisons: take("comparisons", "comparison", cap.comparisons)?,
        integer_digits: take("integer-digits", "digit", cap.integer_digits)?,
        digit_work: take("digit-work", "digit", cap.digit_work)?,
        text_bytes: take("text-bytes", "byte", cap.text_bytes)?,
        path_bytes: take("path-bytes", "byte", cap.path_bytes)?,
        output_bytes: take("output-bytes", "byte", cap.output_bytes)?,
    };
    if !values.is_empty() {
        return Err(invalid("backend limits", "extra entry"));
    }
    Ok(result)
}
