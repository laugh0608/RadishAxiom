//! 类型化、无递归所有权的 SMT DAG。每个引用只指向更早的节点。
use super::{Budget, QueryError, QueryResource, QuerySymbol, Result, SymbolOrigin};

pub(super) type Term = usize;
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) enum Sort {
    Bool,
    Int,
    Text,
}
impl Sort {
    pub fn name(self) -> &'static str {
        match self {
            Self::Bool => "Bool",
            Self::Int => "Int",
            Self::Text => "Text",
        }
    }
}
#[derive(Clone, Copy, Debug)]
pub(super) enum Op {
    Not,
    And,
    Or,
    Eq,
    Lt,
    Le,
    Gt,
    Ge,
    Add,
    Sub,
    Ite,
}
impl Op {
    fn name(self) -> &'static str {
        match self {
            Self::Not => "not",
            Self::And => "and",
            Self::Or => "or",
            Self::Eq => "=",
            Self::Lt => "<",
            Self::Le => "<=",
            Self::Gt => ">",
            Self::Ge => ">=",
            Self::Add => "+",
            Self::Sub => "-",
            Self::Ite => "ite",
        }
    }
}
enum Node {
    Bool(bool),
    Int(String),
    Symbol(Sort),
    App(Sort, Op, Vec<Term>),
}
impl Node {
    fn sort(&self) -> Sort {
        match self {
            Self::Bool(_) => Sort::Bool,
            Self::Int(_) => Sort::Int,
            Self::Symbol(s) | Self::App(s, _, _) => *s,
        }
    }
}
pub(super) struct Arena {
    nodes: Vec<Node>,
    pub budget: Budget,
    prefix: String,
    pub symbols: Vec<QuerySymbol>,
}
impl Arena {
    pub fn new(budget: Budget) -> Result<Self> {
        let prefix = format!("q{}_t", &budget.obligation[7..]);
        let mut arena = Self {
            nodes: Vec::new(),
            budget,
            prefix,
            symbols: Vec::new(),
        };
        arena.push(Node::Bool(false), 0)?;
        arena.push(Node::Bool(true), 0)?;
        Ok(arena)
    }
    pub fn boolean(&self, value: bool) -> Term {
        usize::from(value)
    }
    fn push(&mut self, node: Node, edges: usize) -> Result<Term> {
        self.budget.charge(
            QueryResource::SmtNodes,
            edges
                .checked_add(1)
                .ok_or_else(|| self.budget.error(QueryResource::SmtNodes))?,
        )?;
        let index = self.nodes.len();
        self.nodes.push(node);
        Ok(index)
    }
    pub fn integer(&mut self, value: &str) -> Result<Term> {
        // 数字来自已核验 IR 或有界宿主计数。先预算字符串再复制。
        self.budget.charge(QueryResource::ValueCells, value.len())?;
        self.push(Node::Int(value.to_owned()), 0)
    }
    pub fn symbol(&mut self, sort: Sort, origin: SymbolOrigin) -> Result<Term> {
        let term = self.push(Node::Symbol(sort), 0)?;
        self.symbols.push(QuerySymbol {
            name: format!("{}{term}", self.prefix),
            sort: sort.name(),
            origin,
        });
        Ok(term)
    }
    pub fn app(&mut self, op: Op, args: &[Term]) -> Result<Term> {
        let is = |expected: &[Sort]| {
            args.len() == expected.len()
                && args
                    .iter()
                    .zip(expected)
                    .all(|(&id, s)| self.nodes[id].sort() == *s)
        };
        let sort = match op {
            Op::Not if is(&[Sort::Bool]) => Sort::Bool,
            Op::And | Op::Or if args.iter().all(|&id| self.nodes[id].sort() == Sort::Bool) => {
                Sort::Bool
            }
            Op::Eq
                if args.len() == 2 && self.nodes[args[0]].sort() == self.nodes[args[1]].sort() =>
            {
                Sort::Bool
            }
            Op::Lt | Op::Le | Op::Gt | Op::Ge if is(&[Sort::Int, Sort::Int]) => Sort::Bool,
            Op::Add | Op::Sub if is(&[Sort::Int, Sort::Int]) => Sort::Int,
            Op::Ite
                if args.len() == 3
                    && self.nodes[args[0]].sort() == Sort::Bool
                    && self.nodes[args[1]].sort() == self.nodes[args[2]].sort() =>
            {
                self.nodes[args[1]].sort()
            }
            _ => return Err(QueryError::Internal("ill-typed SMT application")),
        };
        if matches!(op, Op::And | Op::Or) {
            if args.is_empty() {
                return Ok(self.boolean(matches!(op, Op::And)));
            }
            if args.len() == 1 {
                return Ok(args[0]);
            }
        }
        // 分配操作数数组之前检查节点与边；push 不重复计数。
        self.budget.charge(
            QueryResource::SmtNodes,
            args.len()
                .checked_add(1)
                .ok_or_else(|| self.budget.error(QueryResource::SmtNodes))?,
        )?;
        let id = self.nodes.len();
        self.nodes.push(Node::App(sort, op, args.to_vec()));
        Ok(id)
    }
    pub fn and(&mut self, args: &[Term]) -> Result<Term> {
        self.app(Op::And, args)
    }
    pub fn or(&mut self, args: &[Term]) -> Result<Term> {
        self.app(Op::Or, args)
    }
    pub fn not(&mut self, a: Term) -> Result<Term> {
        self.app(Op::Not, &[a])
    }
    pub fn implies(&mut self, a: Term, b: Term) -> Result<Term> {
        let not = self.not(a)?;
        self.or(&[not, b])
    }
    pub fn ite(&mut self, c: Term, a: Term, b: Term) -> Result<Term> {
        self.app(Op::Ite, &[c, a, b])
    }
    pub fn render(mut self, goal: Term) -> Result<(Vec<u8>, Vec<QuerySymbol>, super::QueryUsage)> {
        if self.nodes[goal].sort() != Sort::Bool {
            return Err(QueryError::Internal("non-Boolean goal"));
        }
        let mut size = Some(0usize);
        self.emit(goal, &mut |s| {
            size = size.and_then(|n| n.checked_add(s.len()))
        });
        let size = size.ok_or_else(|| self.budget.error(QueryResource::OutputBytes))?;
        self.budget.charge(QueryResource::OutputBytes, size)?;
        let mut bytes = Vec::with_capacity(size);
        self.emit(goal, &mut |s| bytes.extend_from_slice(s.as_bytes()));
        Ok((bytes, self.symbols, self.budget.usage))
    }
    fn emit(&self, goal: Term, write: &mut impl FnMut(&str)) {
        write("(set-logic QF_UFLIA)\n(declare-sort Text 0)\n");
        for (index, node) in self.nodes.iter().enumerate() {
            let symbol = matches!(node, Node::Symbol(_));
            write(if symbol {
                "(declare-const "
            } else {
                "(define-fun "
            });
            self.reference(index, write);
            write(if symbol { " " } else { " () " });
            write(node.sort().name());
            if !symbol {
                write(" ");
                match node {
                    Node::Bool(v) => write(if *v { "true" } else { "false" }),
                    Node::Int(v) => {
                        if let Some(magnitude) = v.strip_prefix('-') {
                            write("(- ");
                            write(magnitude);
                            write(")");
                        } else {
                            write(v);
                        }
                    }
                    Node::App(_, op, args) => {
                        write("(");
                        write(op.name());
                        for &arg in args {
                            write(" ");
                            self.reference(arg, write);
                        }
                        write(")");
                    }
                    Node::Symbol(_) => unreachable!(),
                }
            }
            write(")\n");
        }
        write("(assert ");
        self.reference(goal, write);
        write(")\n(check-sat)\n");
    }
    fn reference(&self, id: Term, write: &mut impl FnMut(&str)) {
        write(&self.prefix);
        write(&id.to_string());
    }
}
