//! 对索引做可中止的稳定归并排序；不克隆复合项，也不在预算失败后继续比较。
use super::{Budget, Result, SolverResource as R};
use std::cmp::Ordering;

pub(super) fn sorted_indices<T>(
    items: &[T],
    b: &mut Budget,
    mut compare: impl FnMut(&T, &T, &mut Budget) -> Result<Ordering>,
) -> Result<Vec<usize>> {
    b.charge(
        R::ValueCells,
        items
            .len()
            .checked_mul(2)
            .ok_or_else(|| b.error(R::ValueCells))?,
    )?;
    let mut order: Vec<_> = (0..items.len()).collect();
    let mut scratch = vec![0; items.len()];
    let mut width = 1usize;
    while width < items.len() {
        let mut start = 0usize;
        while start < items.len() {
            let middle = start.saturating_add(width).min(items.len());
            let end = middle.saturating_add(width).min(items.len());
            let (mut left, mut right) = (start, middle);
            for destination in &mut scratch[start..end] {
                b.step()?;
                let take_left = if right == end {
                    true
                } else if left == middle {
                    false
                } else {
                    compare(&items[order[left]], &items[order[right]], b)? != Ordering::Greater
                };
                if take_left {
                    *destination = order[left];
                    left += 1;
                } else {
                    *destination = order[right];
                    right += 1;
                }
            }
            start = end;
        }
        std::mem::swap(&mut order, &mut scratch);
        width = width
            .checked_mul(2)
            .ok_or_else(|| b.error(R::DecodeSteps))?;
    }
    Ok(order)
}
