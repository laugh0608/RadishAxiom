use super::{
    Budget, EncodedQuery, QueryBinding, QueryError, QueryLimits, QueryResource, QueryUsage, Result,
    SymbolOrigin, array, get,
    layout::{Data, LayoutId, Layouts},
    planning::Plan,
    smt::{Arena, Op, Sort, Term},
    string, text,
};
use crate::{
    declarations::{EnumType, TableType},
    document::CanonicalDocument,
    json::Value,
    obligations::{ObligationKind, raw_digest},
};
use std::{collections::BTreeMap, rc::Rc};

pub(super) struct Slot {
    pub active: Term,
    pub data: Data,
}
pub(super) struct Table {
    pub slots: Vec<Slot>,
    pub ok: Term,
    pub layout: LayoutId,
    pub keys: Rc<[String]>,
}
pub(super) struct Evaluated {
    pub data: Data,
    pub ok: Term,
}
impl Evaluated {
    pub fn scalar(&self) -> Term {
        self.data.lanes[self.data.start]
    }
}
pub(super) struct Encoder<'a> {
    pub arena: Arena,
    pub layouts: Layouts,
    pub plan: Plan<'a>,
    pub tables: BTreeMap<&'a str, Rc<Table>>,
    pub table_types: BTreeMap<&'a str, &'a TableType>,
    key_names: BTreeMap<&'a str, Rc<[String]>>,
    pub enums: BTreeMap<&'a str, &'a EnumType>,
    pub literals: BTreeMap<&'a str, Term>,
    pub target_anchor: &'a str,
    pub target_path: Vec<&'a str>,
    pub violations: Vec<Term>,
    cardinality_target: bool,
    cardinality_violation: Option<Term>,
}

pub(super) fn encode(
    document: &CanonicalDocument,
    root: &Value,
    definition: &Value,
    kind: ObligationKind,
    binding: QueryBinding,
    limits: QueryLimits,
) -> Result<EncodedQuery> {
    let mut budget = Budget {
        limits,
        usage: QueryUsage::default(),
        obligation: binding.obligation.clone(),
    };
    let plan = Plan::new(document, root, &mut budget)?;
    let types = document.components().analysis().graph().types();
    let subject = get(definition, "subject");
    if kind == ObligationKind::KeyCardinality {
        plan.output_comparisons(document, text(subject, "id"), &mut budget)?;
    }
    let layouts = Layouts::new(types, &mut budget)?;
    let target_path = if kind == ObligationKind::NumericRange {
        array(get(subject, "path")).iter().map(string).collect()
    } else {
        Vec::new()
    };
    let mut encoder = Encoder {
        arena: Arena::new(budget)?,
        layouts,
        plan,
        tables: BTreeMap::new(),
        table_types: types
            .table_types()
            .iter()
            .map(|t| (t.id(), t.definition()))
            .collect(),
        key_names: types
            .table_types()
            .iter()
            .map(|t| (t.id(), Rc::from(t.definition().primary_key.clone())))
            .collect(),
        enums: types
            .enum_types()
            .iter()
            .map(|e| (e.id(), e.definition()))
            .collect(),
        literals: BTreeMap::new(),
        target_anchor: text(subject, "id"),
        target_path,
        violations: Vec::new(),
        cardinality_target: kind == ObligationKind::KeyCardinality,
        cardinality_violation: None,
    };
    for &value in &encoder.plan.literals {
        let term = encoder
            .arena
            .symbol(Sort::Text, SymbolOrigin::TextLiteral(value.to_owned()))?;
        encoder.literals.insert(value, term);
    }
    let literal_terms: Vec<_> = encoder.literals.values().copied().collect();
    let mut wf = Vec::new();
    for (i, &left) in literal_terms.iter().enumerate() {
        for &right in &literal_terms[..i] {
            let equal = encoder.arena.app(Op::Eq, &[left, right])?;
            wf.push(encoder.arena.not(equal)?);
        }
    }
    // 依赖深度 / ID 序不依赖 CanonicalDocument 的原始分析索引。
    for i in 0..encoder.plan.nodes.len() {
        let entry = encoder.plan.nodes[i];
        let id = text(entry, "id");
        let node = get(entry, "definition");
        let table = if text(node, "kind") == "input" {
            encoder.input(id, node, &mut wf)?
        } else {
            encoder.transform(id, node)?
        };
        encoder.tables.insert(id, Rc::new(table));
    }
    let all_ok: Vec<_> = encoder.tables.values().map(|t| t.ok).collect();
    let program_ok = encoder.arena.and(&all_ok)?;
    let mut pre = Vec::new();
    let mut guarantee = None;
    for entry in array(get(root, "contracts")) {
        let contract = get(entry, "definition");
        if text(contract, "kind") != "formula" {
            continue;
        }
        let id = text(entry, "id");
        let assume = text(contract, "role") == "assume";
        // guarantee 是程序完成后观察；Pre 则仅在输入上求值。
        let reach = if assume {
            encoder.arena.boolean(true)
        } else {
            program_ok
        };
        let value = encoder.eval(
            get(contract, "expression"),
            &mut Vec::new(),
            reach,
            id,
            &mut vec!["expression".to_owned()],
        )?;
        let holds = encoder.arena.and(&[value.ok, value.scalar()])?;
        if assume {
            pre.push(holds);
        } else if id == encoder.target_anchor {
            guarantee = Some(encoder.arena.and(&[program_ok, holds])?);
        }
    }
    let violation = match kind {
        ObligationKind::NumericRange => encoder.arena.or(&encoder.violations)?,
        ObligationKind::ContractGuarantee => encoder
            .arena
            .not(guarantee.ok_or(QueryError::Internal("missing guarantee target"))?)?,
        ObligationKind::Totality => {
            // 节点无结果包含依赖故障；无关节点与 guarantee 不参与目标。
            let target = encoder
                .tables
                .get(encoder.target_anchor)
                .ok_or(QueryError::Internal("missing totality target"))?;
            encoder.arena.not(target.ok)?
        }
        ObligationKind::KeyCardinality => encoder
            .cardinality_violation
            .ok_or(QueryError::Internal("missing key-cardinality target"))?,
        _ => return Err(QueryError::UnsupportedKind(kind)),
    };
    let wf = encoder.arena.and(&wf)?;
    let pre = encoder.arena.and(&pre)?;
    let goal = encoder.arena.and(&[wf, pre, violation])?;
    let (bytes, symbols, usage) = encoder.arena.render(goal)?;
    Ok(EncodedQuery {
        artifact_digest: raw_digest(&bytes),
        bytes,
        binding,
        symbols,
        usage,
    })
}

impl Encoder<'_> {
    fn input(&mut self, id: &str, node: &Value, wf: &mut Vec<Term>) -> Result<Table> {
        let ty = self.table_types[text(node, "table_type")];
        let layout = self.layouts.records[&ty.record_type];
        let extent = self.plan.extents[id];
        self.arena
            .budget
            .charge(QueryResource::ValueCells, extent)?;
        let sorts = self.layouts.leaves(layout, &mut self.arena.budget)?;
        let cells = extent
            .checked_mul(sorts.len())
            .ok_or_else(|| self.arena.budget.error(QueryResource::ValueCells))?;
        self.arena.budget.charge(QueryResource::ValueCells, cells)?;
        let mut slots = Vec::with_capacity(extent);
        let interface: std::sync::Arc<str> = text(node, "port").into();
        for slot in 0..extent {
            let active = self.arena.symbol(
                Sort::Bool,
                SymbolOrigin::Input {
                    interface: interface.clone(),
                    slot,
                    component: None,
                },
            )?;
            let mut lanes = Vec::with_capacity(sorts.len());
            for (component, &sort) in sorts.iter().enumerate() {
                lanes.push(self.arena.symbol(
                    sort,
                    SymbolOrigin::Input {
                        interface: interface.clone(),
                        slot,
                        component: Some(component),
                    },
                )?);
            }
            let data = self.layouts.make(layout, lanes);
            let row_wf = self.layouts.wf(&data, &mut self.arena)?;
            wf.push(self.arena.implies(active, row_wf)?);
            slots.push(Slot { active, data });
        }
        for (i, left) in slots.iter().enumerate() {
            for right in &slots[..i] {
                let mut keys = Vec::new();
                for key in &ty.primary_key {
                    keys.push(self.layouts.equal(
                        &self.layouts.field(&left.data, key),
                        &self.layouts.field(&right.data, key),
                        &mut self.arena,
                    )?);
                }
                let equal = self.arena.and(&keys)?;
                let different = self.arena.not(equal)?;
                let both = self.arena.and(&[left.active, right.active])?;
                wf.push(self.arena.implies(both, different)?);
            }
        }
        Ok(Table {
            slots,
            layout,
            keys: self.key_names[text(node, "table_type")].clone(),
            ok: self.arena.boolean(true),
        })
    }
    fn transform(&mut self, id: &str, node: &Value) -> Result<Table> {
        let ty = self.table_types[text(node, "table_type")];
        let source = self.tables[text(node, "source")].clone();
        let layout = self.layouts.records[&ty.record_type];
        self.arena
            .budget
            .charge(QueryResource::ValueCells, source.slots.len())?;
        let mut slots = Vec::with_capacity(source.slots.len());
        let mut success = vec![source.ok];
        for slot in &source.slots {
            let reach = self.arena.and(&[source.ok, slot.active])?;
            let mut env = vec![slot.data.clone()];
            if text(node, "kind") == "filter" {
                let predicate = self.eval(
                    get(node, "predicate"),
                    &mut env,
                    reach,
                    id,
                    &mut vec!["predicate".to_owned()],
                )?;
                success.push(self.arena.implies(slot.active, predicate.ok)?);
                let active = self.arena.and(&[slot.active, predicate.scalar()])?;
                slots.push(Slot {
                    active,
                    data: slot.data.clone(),
                });
            } else {
                let len = self.layouts.entries[layout].len;
                self.arena.budget.charge(QueryResource::ValueCells, len)?;
                let mut lanes = Vec::with_capacity(len);
                for (index, field) in array(get(node, "fields")).iter().enumerate() {
                    let value = self.eval(
                        get(field, "expression"),
                        &mut env,
                        reach,
                        id,
                        &mut vec![
                            "fields".to_owned(),
                            index.to_string(),
                            "expression".to_owned(),
                        ],
                    )?;
                    success.push(self.arena.implies(slot.active, value.ok)?);
                    lanes.extend_from_slice(self.layouts.slice(&value.data));
                }
                slots.push(Slot {
                    active: slot.active,
                    data: self.layouts.make(layout, lanes),
                });
            }
        }
        let mut count = self.arena.integer("0")?;
        let zero = count;
        let one = self.arena.integer("1")?;
        for slot in &slots {
            let contribution = self.arena.ite(slot.active, one, zero)?;
            count = self.arena.app(Op::Add, &[count, contribution])?;
        }
        let capacity = self.arena.integer(ty.capacity.as_str())?;
        let within_capacity = self.arena.app(Op::Le, &[count, capacity])?;
        if self.cardinality_target && id == self.target_anchor {
            // Ready 不含自身容量；故障行仅为占位值，不能制造局部键反例。
            let ready = self.arena.and(&success)?;
            let unique = output_unique(&slots, &ty.primary_key, &self.layouts, &mut self.arena)?;
            let not_unique = self.arena.not(unique)?;
            let not_capacity = self.arena.not(within_capacity)?;
            let failure = self.arena.or(&[not_unique, not_capacity])?;
            self.cardinality_violation = Some(self.arena.and(&[ready, failure])?);
        }
        success.push(within_capacity);
        let ok = self.arena.and(&success)?;
        Ok(Table {
            slots,
            ok,
            layout,
            keys: self.key_names[text(node, "table_type")].clone(),
        })
    }
}

/// 对真实派生槽位比较全部输出键；调用前已由 Plan 预收 N²K 比较成本。
pub(super) fn output_unique(
    slots: &[Slot],
    keys: &[String],
    layouts: &Layouts,
    arena: &mut Arena,
) -> Result<Term> {
    let mut distinct = Vec::new();
    for (i, left) in slots.iter().enumerate() {
        for right in &slots[..i] {
            arena.budget.charge(QueryResource::ValueCells, keys.len())?;
            let mut equal_keys = Vec::with_capacity(keys.len());
            for key in keys {
                equal_keys.push(layouts.equal(
                    &layouts.field(&left.data, key),
                    &layouts.field(&right.data, key),
                    arena,
                )?);
            }
            let equal = arena.and(&equal_keys)?;
            let different = arena.not(equal)?;
            let both = arena.and(&[left.active, right.active])?;
            arena.budget.charge(QueryResource::ValueCells, 1)?;
            distinct.push(arena.implies(both, different)?);
        }
    }
    arena.and(&distinct)
}
