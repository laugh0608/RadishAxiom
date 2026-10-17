//! v0.5：原类型 DAG 的单次保序规范化；不经过旧 SMT 文本。
use super::CompactQueryResource as R;
use super::{
    CompactQueryLimits, CompactQueryUsage, QueryResource, QueryStage, QuerySymbol, QueryUsage,
    Result,
    compact_budget::Meter,
    smt::{Arena, Node as Raw, Op, Sort, Term},
};
#[path = "compact_integer.rs"]
mod integer;
#[path = "compact_render.rs"]
mod rendering;

#[derive(Debug)]
enum Node {
    Bool(bool),
    Int(String),
    Free(Sort, usize),
    App(Sort, Op, Vec<usize>),
}
impl Node {
    fn sort(&self) -> Sort {
        match self {
            Self::Bool(_) => Sort::Bool,
            Self::Int(_) => Sort::Int,
            Self::Free(s, _) | Self::App(s, _, _) => *s,
        }
    }
    fn args(&self) -> &[usize] {
        if let Self::App(_, _, a) = self {
            a
        } else {
            &[]
        }
    }
}
struct Dag {
    nodes: Vec<Node>,
    depths: Vec<usize>,
    // 明确开放寻址表，探测、碰撞比较及扩容复制均可以收费并中止。
    table: Vec<Option<(u64, usize)>>,
    meter: Meter,
}
impl Dag {
    fn new(meter: Meter) -> Self {
        Self {
            nodes: Vec::new(),
            depths: Vec::new(),
            table: Vec::new(),
            meter,
        }
    }
    fn hash(&mut self, node: &Node) -> Result<u64> {
        let mut h = 14695981039346656037u64;
        let mut feed = |b: u8| {
            h = (h ^ u64::from(b)).wrapping_mul(1099511628211);
        };
        self.meter.work(2)?;
        feed(node.sort() as u8);
        match node {
            Node::Bool(v) => {
                feed(0);
                feed(u8::from(*v));
            }
            Node::Int(s) => {
                feed(1);
                for b in s.bytes() {
                    self.meter.work(1)?;
                    feed(b);
                }
            }
            Node::Free(_, id) => {
                feed(2);
                for b in id.to_le_bytes() {
                    self.meter.work(1)?;
                    feed(b);
                }
            }
            Node::App(_, op, args) => {
                feed(3);
                feed(*op as u8);
                for id in args {
                    self.meter.work(std::mem::size_of::<usize>())?;
                    for b in id.to_le_bytes() {
                        feed(b);
                    }
                }
            }
        }
        Ok(h)
    }
    fn same(&mut self, a: &Node, id: usize) -> Result<bool> {
        self.meter.work(1)?;
        let b = &self.nodes[id];
        Ok(match (a, b) {
            (Node::Bool(a), Node::Bool(b)) => a == b,
            (Node::Int(a), Node::Int(b)) => {
                integer::compare_bytes(a, b, &mut self.meter)? == std::cmp::Ordering::Equal
            }
            (Node::Free(s, a), Node::Free(t, b)) => s == t && a == b,
            (Node::App(s, op, a), Node::App(t, oq, b)) => {
                if s != t || op != oq || a.len() != b.len() {
                    false
                } else {
                    let mut same = true;
                    for (a, b) in a.iter().zip(b) {
                        self.meter.work(1)?;
                        if a != b {
                            same = false;
                            break;
                        }
                    }
                    same
                }
            }
            _ => false,
        })
    }
    fn grow(&mut self) -> Result<()> {
        let len = if self.table.is_empty() {
            16
        } else {
            self.meter.mul(self.table.len(), 2, R::ScratchCells)?
        };
        self.meter.cells(len)?;
        let mut next = vec![None; len];
        for entry in self.table.iter().flatten().copied() {
            self.meter.work(1)?;
            let mut index = entry.0 as usize & (len - 1);
            while next[index].is_some() {
                self.meter.work(1)?;
                index = (index + 1) & (len - 1);
            }
            self.meter.cells(1)?;
            self.meter.work(1)?;
            next[index] = Some(entry);
        }
        self.table = next;
        Ok(())
    }
    fn intern(&mut self, node: Node) -> Result<usize> {
        let hash = self.hash(&node)?;
        if self.table.is_empty() || self.nodes.len() >= self.table.len() / 2 {
            self.grow()?;
        }
        let mut index = hash as usize & (self.table.len() - 1);
        while let Some((h, id)) = self.table[index] {
            self.meter.work(1)?;
            if h == hash && self.same(&node, id)? {
                return Ok(id);
            }
            index = (index + 1) & (self.table.len() - 1);
        }
        self.meter.work(1)?;
        let mut depth = 1;
        for &arg in node.args() {
            self.meter.work(1)?;
            depth = depth.max(self.meter.add(self.depths[arg], 1, R::DagDepth)?);
        }
        self.meter.charge(R::DagDepth, depth)?;
        self.meter.charge(R::NormalizedNodes, 1)?;
        self.meter.charge(R::NormalizedEdges, node.args().len())?;
        // node / depth / table entry are persistent scratch records.
        self.meter.cells(3)?;
        let id = self.nodes.len();
        self.nodes.push(node);
        self.depths.push(depth);
        self.table[index] = Some((hash, id));
        Ok(id)
    }
    fn boolean(&mut self, value: bool) -> Result<usize> {
        self.intern(Node::Bool(value))
    }
    fn int(&mut self, value: &str) -> Result<usize> {
        self.meter.charge(
            R::IntegerDigits,
            value.len() - usize::from(value.starts_with('-')),
        )?;
        let value = self.meter.copy(value)?;
        self.intern(Node::Int(value))
    }
    fn bool_value(&self, id: usize) -> Option<bool> {
        if let Node::Bool(v) = self.nodes[id] {
            Some(v)
        } else {
            None
        }
    }
    fn app(&mut self, sort: Sort, op: Op, mut a: Vec<usize>) -> Result<usize> {
        // 每个规则有固定有界分支；预付全部12个分支的保守上界，逐边循环另行收费。
        self.meter.work(12)?;
        match op {
            Op::Not => {
                if let Some(v) = self.bool_value(a[0]) {
                    return self.boolean(!v);
                }
                if let Node::App(_, Op::Not, ref args) = self.nodes[a[0]] {
                    return Ok(args[0]);
                }
            }
            Op::And | Op::Or => {
                let identity = op == Op::And;
                // 吸收优先；不能因为先去重改变插入顺序。
                for &id in &a {
                    self.meter.work(1)?;
                    if self.bool_value(id) == Some(!identity) {
                        return self.boolean(!identity);
                    }
                }
                self.meter.cells(a.len())?;
                let mut filtered = Vec::with_capacity(a.len());
                // ID 去重使用可中止开放寻址，避免高元数线性查找的平方路径。
                let size = a
                    .len()
                    .checked_mul(2)
                    .and_then(|n| n.checked_add(1))
                    .and_then(|n| n.checked_next_power_of_two())
                    .ok_or_else(|| self.meter.error(R::ScratchCells))?;
                self.meter.cells(size)?;
                let mut seen = vec![None; size];
                for id in a {
                    self.meter.work(1)?;
                    if self.bool_value(id) == Some(identity) {
                        continue;
                    }
                    let mut at = id.wrapping_mul(0x9e3779b9) & (size - 1);
                    while let Some(previous) = seen[at] {
                        self.meter.work(1)?;
                        if previous == id {
                            break;
                        }
                        at = (at + 1) & (size - 1);
                    }
                    self.meter.work(1)?;
                    if seen[at].is_none() {
                        seen[at] = Some(id);
                        filtered.push(id);
                    }
                }
                if filtered.is_empty() {
                    return self.boolean(identity);
                }
                if filtered.len() == 1 {
                    return Ok(filtered[0]);
                }
                a = filtered;
            }
            Op::Eq => {
                if a[0] == a[1] {
                    return self.boolean(true);
                }
                let comparison = match (&self.nodes[a[0]], &self.nodes[a[1]]) {
                    (Node::Bool(a), Node::Bool(b)) => Some(a == b),
                    (Node::Int(a), Node::Int(b)) => Some(
                        integer::compare_bytes(a, b, &mut self.meter)? == std::cmp::Ordering::Equal,
                    ),
                    _ => None,
                };
                if let Some(v) = comparison {
                    return self.boolean(v);
                }
                if a[0] > a[1] {
                    a.swap(0, 1);
                }
            }
            Op::Add | Op::Sub => {
                if let (Node::Int(left), Node::Int(right)) = (&self.nodes[a[0]], &self.nodes[a[1]])
                {
                    let value = integer::calculate(left, right, op == Op::Sub, &mut self.meter)?;
                    return self.intern(Node::Int(value));
                }
                if matches!(&self.nodes[a[1]], Node::Int(v) if v=="0") {
                    return Ok(a[0]);
                }
                if op == Op::Add && matches!(&self.nodes[a[0]],Node::Int(v) if v=="0") {
                    return Ok(a[1]);
                }
                if op == Op::Sub && a[0] == a[1] {
                    return self.int("0");
                }
            }
            Op::Lt | Op::Le | Op::Gt | Op::Ge => {
                if a[0] == a[1] {
                    return self.boolean(matches!(op, Op::Le | Op::Ge));
                }
                if let (Node::Int(left), Node::Int(right)) = (&self.nodes[a[0]], &self.nodes[a[1]])
                {
                    let cmp = integer::compare(left, right, &mut self.meter)?;
                    return self.boolean(match op {
                        Op::Lt => cmp.is_lt(),
                        Op::Le => !cmp.is_gt(),
                        Op::Gt => cmp.is_gt(),
                        _ => !cmp.is_lt(),
                    });
                }
            }
            Op::Ite => {
                if let Some(v) = self.bool_value(a[0]) {
                    return Ok(a[if v { 1 } else { 2 }]);
                }
                if a[1] == a[2] {
                    return Ok(a[1]);
                }
                if sort == Sort::Bool {
                    match (self.bool_value(a[1]), self.bool_value(a[2])) {
                        (Some(true), Some(false)) => return Ok(a[0]),
                        (Some(false), Some(true)) => {
                            self.meter.cells(1)?;
                            return self.app(Sort::Bool, Op::Not, vec![a[0]]);
                        }
                        _ => {}
                    }
                }
            }
        }
        self.intern(Node::App(sort, op, a))
    }
}
pub(super) fn render(
    mut arena: Arena,
    goal: Term,
    limits: CompactQueryLimits,
) -> Result<(Vec<u8>, Vec<QuerySymbol>, QueryUsage, CompactQueryUsage)> {
    if arena.nodes[goal].sort() != Sort::Bool {
        return Err(super::QueryError::Internal("non-Boolean goal"));
    }
    let meter = arena.compact.take().ok_or(super::QueryError::Internal(
        "missing compact construction meter",
    ))?;
    debug_assert_eq!(meter.limits, limits);
    let mut dag = Dag::new(meter);
    dag.meter.stage = QueryStage::Normalization;
    let n = arena.nodes.len();
    dag.meter.cells(n)?;
    let mut mapping = Vec::with_capacity(n);
    for (id, node) in arena.nodes.iter().enumerate() {
        dag.meter.work(1)?;
        let normalized = match node {
            Raw::Bool(v) => dag.boolean(*v)?,
            Raw::Int(v) => dag.int(v)?,
            Raw::Symbol(s) => dag.intern(Node::Free(*s, id))?,
            Raw::App(s, op, args) => {
                dag.meter.cells(args.len())?;
                let mut converted = Vec::with_capacity(args.len());
                for &arg in args {
                    dag.meter.work(1)?;
                    converted.push(mapping[arg]);
                }
                dag.app(*s, *op, converted)?
            }
        };
        mapping.push(normalized);
    }
    let root = mapping[goal];
    let (bytes, symbols) = rendering::render(&mut dag, root, &mapping, &mut arena)?;
    arena.budget.usage.output_bytes = bytes.len();
    Ok((bytes, symbols, arena.budget.usage, dag.meter.usage))
}

#[cfg(test)]
#[path = "compact_tests.rs"]
mod tests;
