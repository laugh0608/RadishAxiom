//! 可达裁剪、保序自由名称与固定成本代入。
use super::{Arena, Dag, Node, QueryResource, QueryStage, QuerySymbol, R, Result};

fn digits(mut n: usize) -> usize {
    let mut count = 1;
    while n >= 10 {
        n /= 10;
        count += 1;
    }
    count
}
fn name(prefix: char, n: usize, width: usize, d: &mut Dag) -> Result<String> {
    let len = d.meter.add(1, width.max(digits(n)), R::TemporaryBytes)?;
    d.meter.bytes(len)?;
    Ok(format!("{prefix}{n:0width$}"))
}
fn append(buffer: &mut String, value: &str, d: &mut Dag) -> Result<()> {
    d.meter.work(value.len().max(1))?;
    buffer.push_str(value);
    Ok(())
}
fn output(
    lines: &mut Vec<String>,
    value: String,
    d: &mut Dag,
    total: &mut usize,
    arena: &mut Arena,
) -> Result<()> {
    d.meter.work(1)?;
    *total = total
        .checked_add(value.len())
        .ok_or_else(|| arena.budget.error(QueryResource::OutputBytes))?;
    // 最终制品预算在拷贝至最终制品前累计；行缓冲仍单独计临时字节。
    if *total > arena.budget.limits.max_output_bytes {
        return Err(arena.budget.error(QueryResource::OutputBytes));
    }
    d.meter.cells(1)?;
    lines.push(value);
    Ok(())
}
pub(super) fn render(
    d: &mut Dag,
    root: usize,
    mapping: &[usize],
    arena: &mut Arena,
) -> Result<(Vec<u8>, Vec<QuerySymbol>)> {
    d.meter.stage = QueryStage::Rendering;
    let n = d.nodes.len();
    d.meter.cells(d.meter.mul(n, 4, R::ScratchCells)?)?;
    let mut reachable = vec![false; n];
    let mut uses = vec![0usize; n];
    let mut references: Vec<Option<String>> = (0..n).map(|_| None).collect();
    let mut heights = vec![0usize; n];
    d.meter.cells(1)?;
    let mut stack = vec![root];
    while let Some(id) = stack.pop() {
        d.meter.work(1)?;
        if reachable[id] {
            continue;
        }
        reachable[id] = true;
        for &arg in d.nodes[id].args() {
            d.meter.work(1)?;
            d.meter.cells(1)?;
            stack.push(arg);
        }
    }
    uses[root] = 1;
    for (id, node) in d.nodes.iter().enumerate() {
        d.meter.work(1)?;
        if reachable[id] {
            for &arg in node.args() {
                d.meter.work(1)?;
                uses[arg] = d.meter.add(uses[arg], 1, R::WorkSteps)?;
            }
        }
    }
    // 自由项以旧完整ASCII名排序。前缀完全相同，因此只需比较原term ID十进制。
    let count = arena.symbols.len();
    d.meter.cells(count)?;
    let mut order = Vec::with_capacity(count);
    for (id, node) in arena.nodes.iter().enumerate() {
        d.meter.work(1)?;
        if matches!(node, super::Raw::Symbol(_)) {
            order.push(id);
        }
    }
    // 自底向上的稳定归并排序，可在每个字符串字节比较中停止。
    d.meter.cells(count)?;
    let mut temporary = vec![0usize; count];
    let mut run = 1;
    while run < count {
        let mut start = 0;
        while start < count {
            let mid = d.meter.add(start, run, R::WorkSteps)?.min(count);
            let end = d.meter.add(mid, run, R::WorkSteps)?.min(count);
            let (mut left, mut right, mut at) = (start, mid, start);
            while left < mid || right < end {
                d.meter.work(1)?;
                let take_left = if right == end {
                    true
                } else if left == mid {
                    false
                } else {
                    // 各ID最多usize十进制宽度；栈缓冲不分配String。
                    compare_ids(order[left], order[right], d)?.is_le()
                };
                d.meter.cells(1)?;
                temporary[at] = if take_left {
                    let v = order[left];
                    left += 1;
                    v
                } else {
                    let v = order[right];
                    right += 1;
                    v
                };
                at += 1;
            }
            start = end;
        }
        std::mem::swap(&mut order, &mut temporary);
        run = run
            .checked_mul(2)
            .ok_or_else(|| d.meter.error(R::WorkSteps))?;
    }
    let width = digits(count.saturating_sub(1));
    d.meter.cells(count)?;
    let mut symbols = Vec::with_capacity(count);
    // 原symbols按term构造顺序，索引映射避免按origin重新构造或丢失闲置声明。
    d.meter.cells(arena.nodes.len())?;
    let mut symbol_index = vec![None; arena.nodes.len()];
    let mut si = 0;
    for (id, node) in arena.nodes.iter().enumerate() {
        d.meter.work(1)?;
        if matches!(node, super::Raw::Symbol(_)) {
            symbol_index[id] = Some(si);
            si += 1;
        }
    }
    let mut lines = Vec::new();
    let mut total = 0;
    let preamble = d
        .meter
        .copy("(set-logic QF_UFLIA)\n(declare-sort Text 0)\n")?;
    output(&mut lines, preamble, d, &mut total, arena)?;
    for (rank, raw) in order.into_iter().enumerate() {
        d.meter.work(1)?;
        let new_name = name('s', rank, width, d)?;
        let symbol = &arena.symbols[symbol_index[raw].expect("free index")];
        let length = d
            .meter
            .add(18 + symbol.sort.len(), new_name.len(), R::TemporaryBytes)?;
        d.meter.bytes(length)?;
        let line = format!("(declare-const {} {})\n", new_name, symbol.sort);
        let reference = d.meter.copy(&new_name)?;
        references[mapping[raw]] = Some(reference);
        // origin is retained by moving after rendering; this clone's variable string is charged.
        if let super::super::SymbolOrigin::TextLiteral(value) = &symbol.origin {
            d.meter.bytes(value.len())?;
        }
        symbols.push(QuerySymbol {
            name: new_name,
            sort: symbol.sort,
            origin: symbol.origin.clone(),
        });
        output(&mut lines, line, d, &mut total, arena)?;
    }
    let mut definitions = 0;
    for id in 0..n {
        d.meter.work(1)?;
        if !reachable[id] || matches!(d.nodes[id], Node::Free(_, _)) {
            continue;
        }
        let (length, height) = match &d.nodes[id] {
            Node::Bool(v) => (if *v { 4 } else { 5 }, 0),
            Node::Int(v) => (
                d.meter.add(
                    v.len(),
                    if v.starts_with('-') { 3 } else { 0 },
                    R::TemporaryBytes,
                )?,
                0,
            ),
            Node::App(_, op, args) => {
                let mut length = 2 + op.name().len();
                let mut height = 0;
                for &arg in args {
                    d.meter.work(1)?;
                    length = d.meter.add(length, 1, R::TemporaryBytes)?;
                    length = d.meter.add(
                        length,
                        references[arg].as_ref().expect("earlier reference").len(),
                        R::TemporaryBytes,
                    )?;
                    height = height.max(heights[arg]);
                }
                (length, d.meter.add(height, 1, R::DagDepth)?)
            }
            Node::Free(_, _) => unreachable!(),
        };
        // No allocation of expression text occurs before its full checked length is known.
        if length > arena.budget.limits.max_output_bytes {
            return Err(arena.budget.error(QueryResource::OutputBytes));
        }
        d.meter.bytes(length)?;
        let mut expression = String::with_capacity(length);
        // Temporarily take the node so mutable metering does not require cloning the DAG.
        let node = std::mem::replace(&mut d.nodes[id], Node::Bool(false));
        match &node {
            Node::Bool(v) => append(&mut expression, if *v { "true" } else { "false" }, d)?,
            Node::Int(v) => {
                if let Some(magnitude) = v.strip_prefix('-') {
                    append(&mut expression, "(- ", d)?;
                    append(&mut expression, magnitude, d)?;
                    append(&mut expression, ")", d)?;
                } else {
                    append(&mut expression, v, d)?;
                }
            }
            Node::App(_, op, args) => {
                append(&mut expression, "(", d)?;
                append(&mut expression, op.name(), d)?;
                for &arg in args {
                    append(&mut expression, " ", d)?;
                    append(&mut expression, references[arg].as_ref().unwrap(), d)?;
                }
                append(&mut expression, ")", d)?;
            }
            Node::Free(_, _) => unreachable!(),
        }
        let candidate = name('d', definitions, 1, d)?;
        d.meter.work(4)?;
        let definition_len = d.meter.add(
            d.meter.add(
                19 + node.sort().name().len(),
                candidate.len(),
                R::TemporaryBytes,
            )?,
            length,
            R::TemporaryBytes,
        )?;
        let inline = choose_inline(
            matches!(node, Node::Bool(_) | Node::Int(_)),
            uses[id],
            length,
            height,
            definition_len,
            candidate.len(),
            &mut d.meter,
        )?;
        if inline {
            references[id] = Some(expression);
            heights[id] = height;
        } else {
            d.meter.bytes(definition_len)?;
            let line = format!(
                "(define-fun {} () {} {})\n",
                candidate,
                node.sort().name(),
                expression
            );
            output(&mut lines, line, d, &mut total, arena)?;
            references[id] = Some(candidate);
            definitions = d.meter.add(definitions, 1, R::WorkSteps)?;
        }
        d.nodes[id] = node;
    }
    let reference = references[root].as_ref().expect("root reference");
    let length = d.meter.add(22, reference.len(), R::TemporaryBytes)?;
    d.meter.bytes(length)?;
    output(
        &mut lines,
        format!("(assert {reference})\n(check-sat)\n"),
        d,
        &mut total,
        arena,
    )?;
    arena.budget.charge(QueryResource::OutputBytes, total)?;
    let mut bytes = Vec::with_capacity(total);
    for line in lines {
        d.meter.work(line.len())?;
        bytes.extend_from_slice(line.as_bytes());
    }
    Ok((bytes, symbols))
}
fn compare_ids(a: usize, b: usize, d: &mut Dag) -> Result<std::cmp::Ordering> {
    fn ascii(mut n: usize) -> ([u8; 20], usize) {
        let mut a = [0; 20];
        let mut pos = 20;
        loop {
            pos -= 1;
            a[pos] = b'0' + (n % 10) as u8;
            n /= 10;
            if n == 0 {
                break;
            }
        }
        (a, pos)
    }
    d.meter.work(1)?;
    d.meter.work(digits(a) + digits(b))?;
    let (a, ap) = ascii(a);
    let (b, bp) = ascii(b);
    for (a, b) in a[ap..].iter().zip(&b[bp..]) {
        d.meter.work(2)?;
        let cmp = a.cmp(b);
        if !cmp.is_eq() {
            return Ok(cmp);
        }
    }
    Ok((20 - ap).cmp(&(20 - bp)))
}

pub(super) fn choose_inline(
    constant: bool,
    uses: usize,
    length: usize,
    height: usize,
    definition: usize,
    name: usize,
    meter: &mut super::Meter,
) -> Result<bool> {
    // Fixed v0.5 policy. All arithmetic is checked even though common cases are tiny.
    meter.work(8)?;
    let multi = if uses > 1 && length <= 32 && height <= 8 {
        meter.mul(uses, length, R::WorkSteps)?
            < meter.add(
                definition,
                meter.mul(uses, name, R::WorkSteps)?,
                R::WorkSteps,
            )?
    } else {
        false
    };
    Ok((constant && length <= 16) || (uses == 1 && length <= 128 && height <= 8) || multi)
}
