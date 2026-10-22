//! 直接来源的选择与实际候选输出之间的双向键关系；不假定槽位顺序。
use super::encode::Slot;
use super::layout::Layouts;
use super::smt::{Arena, Op, Term};
use super::{Budget, QueryError, QueryResource, Result, array, get, text};
use crate::json::Value;

/// 返回 (来源字段, 输出字段)，顺序为规范输出主键顺序。P1 已核验直接投影。
pub(super) fn key_fields<'a>(
    node: &'a Value,
    keys: &'a [String],
    budget: &mut Budget,
) -> Result<Vec<(&'a str, &'a str)>> {
    budget.charge(QueryResource::ValueCells, keys.len())?;
    let mut result = Vec::with_capacity(keys.len());
    for key in keys {
        let source = if text(node, "kind") == "filter" {
            key.as_str()
        } else {
            let field = array(get(node, "fields"))
                .iter()
                .find(|f| text(f, "name") == key)
                .ok_or(QueryError::Internal("missing output key projection"))?;
            text(get(field, "expression"), "field")
        };
        result.push((source, key.as_str()));
    }
    Ok(result)
}

/// 配对成本已在 Plan 按 Ns × No × K 预收；流式累计，不分配完整匹配矩阵。
pub(super) fn relation(
    source: &[Slot],
    selected: &[Term],
    output: &[Slot],
    keys: &[(&str, &str)],
    layouts: &Layouts,
    arena: &mut Arena,
) -> Result<Term> {
    if selected.len() != source.len() {
        return Err(QueryError::Internal("coverage selection shape"));
    }
    let cells = source
        .len()
        .checked_add(output.len())
        .and_then(|n| n.checked_add(output.len()))
        .ok_or_else(|| arena.budget.error(QueryResource::ValueCells))?;
    arena.budget.charge(QueryResource::ValueCells, cells)?;
    let zero = arena.integer("0")?;
    let one = arena.integer("1")?;
    let mut back_counts = vec![zero; output.len()];
    let mut forward = Vec::with_capacity(source.len());
    let mut backward = Vec::with_capacity(output.len());
    for (i, left) in source.iter().enumerate() {
        let mut count = zero;
        for (j, right) in output.iter().enumerate() {
            arena.budget.charge(QueryResource::ValueCells, keys.len())?;
            let mut components = Vec::with_capacity(keys.len());
            for &(from, to) in keys {
                components.push(layouts.equal(
                    &layouts.field(&left.data, from),
                    &layouts.field(&right.data, to),
                    arena,
                )?);
            }
            let matches = arena.and(&components)?;
            let present = arena.and(&[right.active, matches])?;
            let add = arena.ite(present, one, zero)?;
            count = arena.app(Op::Add, &[count, add])?;
            let chosen = arena.and(&[selected[i], matches])?;
            let add = arena.ite(chosen, one, zero)?;
            back_counts[j] = arena.app(Op::Add, &[back_counts[j], add])?;
        }
        let exactly_one = arena.app(Op::Eq, &[count, one])?;
        forward.push(arena.implies(selected[i], exactly_one)?);
    }
    for (right, count) in output.iter().zip(back_counts) {
        let exactly_one = arena.app(Op::Eq, &[count, one])?;
        backward.push(arena.implies(right.active, exactly_one)?);
    }
    let forward = arena.and(&forward)?;
    let backward = arena.and(&backward)?;
    arena.and(&[forward, backward])
}

pub(super) fn violation(ready: Term, relation: Term, arena: &mut Arena) -> Result<Term> {
    let failure = arena.not(relation)?;
    arena.and(&[ready, failure])
}

/// 只在测试构建导出已有 term 引用；不新增求值项或改变生产制品、预算。
#[cfg(test)]
#[derive(Clone, Debug, Eq, PartialEq)]
pub(super) struct Trace {
    pub ready: Term,
    pub selected: Vec<Term>,
    pub expected_keys: Vec<Vec<Term>>,
    pub output: Vec<(Term, Vec<Term>)>,
}
#[cfg(test)]
impl Trace {
    pub fn new(
        ready: Term,
        source: &[Slot],
        selected: &[Term],
        output: &[Slot],
        keys: &[(&str, &str)],
        layouts: &Layouts,
    ) -> Self {
        Self {
            ready,
            selected: selected.to_vec(),
            expected_keys: source
                .iter()
                .map(|s| {
                    keys.iter()
                        .map(|(from, _)| {
                            let field = layouts.field(&s.data, from);
                            // P1 主键不允许 Record / Option，精确一个标量叶。
                            layouts.slice(&field)[0]
                        })
                        .collect()
                })
                .collect(),
            output: output
                .iter()
                .map(|s| (s.active, layouts.slice(&s.data).to_vec()))
                .collect(),
        }
    }
}
