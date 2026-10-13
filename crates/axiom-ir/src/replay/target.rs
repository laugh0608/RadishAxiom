use super::{
    ReplayOutcome, ReplayResource as R, Result, arithmetic, array,
    budget::Budget,
    engine::{Detail, Engine, Observation, Val},
    get, text,
};
use crate::obligations::ObligationKind;
use std::cmp::Ordering;

impl<'a> Engine<'a> {
    pub(super) fn target(&mut self, b: &mut Budget) -> Result<(Observation<'a>, ReplayOutcome)> {
        let id = self.target_anchor;
        let (violated, detail) = match self.kind {
            ObligationKind::NumericRange => {
                if let Some(c) = array(get(self.ir, "contracts"))
                    .iter()
                    .find(|c| text(c, "id") == id)
                {
                    let d = get(c, "definition");
                    if text(d, "role") == "guarantee" && self.computed.values().all(|t| t.ok) {
                        let _ = self.eval(
                            get(d, "expression"),
                            &mut Vec::new(),
                            id,
                            &mut vec![b.copy("expression")?],
                            b,
                        )?;
                    }
                }
                (
                    self.range.is_some(),
                    if self.range.is_some() {
                        Detail::RangeViolation
                    } else {
                        Detail::RangeHolds
                    },
                )
            }
            ObligationKind::ContractGuarantee => {
                let fault = self.nodes.iter().find_map(|n| {
                    let t = &self.computed[text(n, "id")];
                    if t.ok { None } else { t.cause }
                });
                if let Some(c) = fault {
                    (
                        true,
                        Detail::Guarantee {
                            contract: id,
                            reason: Some("program-fault"),
                            cause: Some(c),
                            location: None,
                        },
                    )
                } else {
                    let c = array(get(self.ir, "contracts"))
                        .iter()
                        .find(|c| text(c, "id") == id)
                        .expect("P2 guarantee");
                    let mut path = vec![b.copy("expression")?];
                    let value = self.eval(
                        get(get(c, "definition"), "expression"),
                        &mut Vec::new(),
                        id,
                        &mut path,
                        b,
                    )?;
                    match value {
                        Err(c) => (
                            true,
                            Detail::Guarantee {
                                contract: id,
                                reason: Some("formula-fault"),
                                cause: None,
                                location: Some(self.root_location(c)),
                            },
                        ),
                        Ok(v) => {
                            let Val::Bool(holds) = self.values[v] else {
                                unreachable!()
                            };
                            let location = if holds {
                                None
                            } else {
                                Some(self.location(id, &path, b)?)
                            };
                            (
                                !holds,
                                Detail::Guarantee {
                                    contract: id,
                                    reason: if holds { None } else { Some("false") },
                                    cause: None,
                                    location,
                                },
                            )
                        }
                    }
                }
            }
            ObligationKind::Totality => {
                let t = &self.computed[id];
                (
                    !t.ok,
                    Detail::Totality {
                        node: id,
                        cause: t.cause,
                    },
                )
            }
            ObligationKind::KeyCardinality => {
                let t = &self.computed[id];
                let table = self.table_type(id);
                let mut rows = Vec::new();
                let mut key = Vec::new();
                let mut reason = None;
                if t.ready {
                    for i in 1..t.rows.len() {
                        b.step()?;
                        if self.row_cmp(t.rows[i - 1], t.rows[i], table, b)? == Ordering::Equal {
                            reason = Some("duplicate-key");
                            b.charge(R::ValueCells, 2)?;
                            rows = vec![i - 1, i];
                            key = self.key(t.rows[i], table, b)?;
                            break;
                        }
                    }
                    if reason.is_none()
                        && arithmetic::compare(
                            &arithmetic::parse(&t.rows.len().to_string(), b)?,
                            &table.capacity,
                            b,
                        )? == Ordering::Greater
                    {
                        reason = Some("capacity");
                    }
                }
                (
                    reason.is_some(),
                    Detail::Cardinality {
                        node: id,
                        ready: t.ready,
                        cause: t.cause,
                        reason,
                        rows,
                        key,
                        actual: t.rows.len(),
                        capacity: table.capacity.as_str(),
                    },
                )
            }
            ObligationKind::RowCoverage => {
                let t = &self.computed[id];
                if !t.ready {
                    (
                        false,
                        Detail::Coverage {
                            node: id,
                            ready: false,
                            cause: t.cause,
                            direction: None,
                            key: Vec::new(),
                            matches: 0,
                        },
                    )
                } else {
                    let def = self.node_definition(id);
                    let table = self.table_type(id);
                    let mut expected = Vec::new();
                    let mut actual = Vec::new();
                    b.charge(R::ValueCells, t.selected.len() + t.rows.len())?;
                    for &row in t.selected.iter() {
                        b.step()?;
                        if text(def, "kind") == "filter" {
                            expected.push(self.key(row, table, b)?);
                        } else {
                            let Val::Record(ty, fields) = &self.values[row] else {
                                unreachable!()
                            };
                            let mut key = Vec::new();
                            b.charge(R::ValueCells, table.primary_key.len())?;
                            for name in &table.primary_key {
                                let f = array(get(def, "fields"))
                                    .iter()
                                    .find(|f| text(f, "name") == name)
                                    .expect("P1 key projection");
                                let source = text(get(f, "expression"), "field");
                                key.push(
                                    fields[self.records[ty]
                                        .fields
                                        .iter()
                                        .position(|f| f.name == source)
                                        .expect("P1 source field")],
                                );
                            }
                            expected.push(key);
                        }
                    }
                    for &row in t.rows.iter() {
                        actual.push(self.key(row, table, b)?);
                    }
                    let failure = self.coverage(&mut expected, &mut actual, b)?;
                    let (direction, key, matches) = match failure {
                        Some((d, k, m)) => (Some(d), k, m),
                        None => (None, Vec::new(), 0),
                    };
                    (
                        direction.is_some(),
                        Detail::Coverage {
                            node: id,
                            ready: true,
                            cause: None,
                            direction,
                            key,
                            matches,
                        },
                    )
                }
            }
            _ => unreachable!("supported target"),
        };
        Ok(if violated {
            (
                Observation::Violated { detail },
                ReplayOutcome::TargetViolated,
            )
        } else {
            (
                Observation::Holds { detail },
                ReplayOutcome::TargetNotViolated,
            )
        })
    }
    pub(super) fn coverage(
        &self,
        expected: &mut [Vec<usize>],
        actual: &mut [Vec<usize>],
        b: &mut Budget,
    ) -> Result<Option<(&'static str, Vec<usize>, usize)>> {
        for keys in [&mut *expected, &mut *actual] {
            for i in 1..keys.len() {
                let mut n = i;
                while n > 0 {
                    b.step()?;
                    if self.key_cmp(&keys[n - 1], &keys[n], b)? != Ordering::Greater {
                        break;
                    }
                    keys.swap(n - 1, n);
                    n -= 1;
                }
            }
        }
        for (direction, left, right) in [
            ("forward", &*expected, &*actual),
            ("backward", &*actual, &*expected),
        ] {
            for key in left {
                let mut matches = 0usize;
                for other in right {
                    b.step()?;
                    if self.key_cmp(key, other, b)? == Ordering::Equal {
                        matches += 1;
                    }
                }
                if matches != 1 {
                    b.charge(R::ValueCells, key.len())?;
                    return Ok(Some((direction, key.clone(), matches)));
                }
            }
        }
        Ok(None)
    }
}
