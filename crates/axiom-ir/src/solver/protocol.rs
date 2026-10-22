//! 固定文法的流式 parser；不构建递归 S-expression 所有权，也不执行一般 SMT term。
use super::{
    encoding::{self, obj, s},
    *,
};
use crate::{integer::Integer, json::Value, obligations::raw_digest};
use std::collections::BTreeSet;

#[derive(Clone, Copy)]
struct Token<'a> {
    text: &'a str,
    offset: usize,
}
struct Parser<'a, 'b> {
    source: &'a str,
    at: usize,
    look: Option<Token<'a>>,
    depth: usize,
    status: Option<SolverStatus>,
    budget: &'b mut Budget,
}
impl<'a> Parser<'a, '_> {
    fn error(&self, offset: usize, reason: &'static str) -> SolverError {
        SolverError::Protocol {
            offset,
            reason,
            reported_status: self.status,
        }
    }
    fn next(&mut self) -> Result<Option<Token<'a>>> {
        if let Some(token) = self.look.take() {
            return Ok(Some(token));
        }
        let bytes = self.source.as_bytes();
        loop {
            while self.at < bytes.len() && matches!(bytes[self.at], b' ' | b'\t' | b'\r' | b'\n') {
                self.at += 1;
            }
            if bytes.get(self.at) != Some(&b';') {
                break;
            }
            while self.at < bytes.len() && !matches!(bytes[self.at], b'\r' | b'\n') {
                self.at += 1;
            }
        }
        if self.at == bytes.len() {
            return Ok(None);
        }
        let start = self.at;
        if matches!(bytes[start], b'(' | b')') {
            self.at += 1;
        } else {
            while self.at < bytes.len()
                && !matches!(
                    bytes[self.at],
                    b' ' | b'\t' | b'\r' | b'\n' | b'(' | b')' | b';'
                )
            {
                self.at += 1;
            }
        }
        self.budget.charge(SolverResource::Tokens, 1)?;
        // 每个词法项保守计一个节点及一条语法边，收费先于返回 token。
        self.budget.charge(SolverResource::SyntaxNodes, 2)?;
        let token = Token {
            text: &self.source[start..self.at],
            offset: start,
        };
        if token.text == "(" {
            self.depth = self
                .depth
                .checked_add(1)
                .ok_or_else(|| self.budget.error(SolverResource::SyntaxDepth))?;
            self.budget
                .observe(SolverResource::SyntaxDepth, self.depth)?;
        }
        if token.text == ")" {
            if self.depth == 0 {
                return Err(self.error(start, "unmatched-close"));
            }
            self.depth -= 1;
        }
        Ok(Some(token))
    }
    fn take(&mut self) -> Result<Token<'a>> {
        self.next()?
            .ok_or_else(|| self.error(self.source.len(), "unexpected-end"))
    }
    fn expect(&mut self, text: &str) -> Result<()> {
        let t = self.take()?;
        if t.text != text {
            return Err(self.error(t.offset, "unexpected-token"));
        }
        Ok(())
    }
    fn peek(&mut self) -> Result<Option<Token<'a>>> {
        if self.look.is_none() {
            self.look = self.next()?;
        }
        Ok(self.look)
    }
    fn numeral(&mut self, t: Token<'_>, positive: bool) -> Result<()> {
        let valid = (t.text == "0" && !positive)
            || (t
                .text
                .as_bytes()
                .first()
                .is_some_and(|b| (b'1'..=b'9').contains(b))
                && t.text.bytes().all(|b| b.is_ascii_digit()));
        if !valid {
            return Err(self.error(t.offset, "noncanonical-integer"));
        }
        self.budget
            .observe(SolverResource::IntegerDigits, t.text.len())
    }
    fn atom(&mut self, t: Token<'_>) -> Result<String> {
        let digits = t
            .text
            .strip_prefix("@Text_")
            .ok_or_else(|| self.error(t.offset, "unsupported-text-atom"))?;
        self.numeral(
            Token {
                text: digits,
                offset: t.offset + 6,
            },
            false,
        )?;
        self.budget.copy(t.text)
    }
}
enum Term {
    Value(Arc<ModelValue>),
    Alias(String),
}
struct Definition {
    sort: Sort,
    term: Term,
    offset: usize,
}

fn value(p: &mut Parser<'_, '_>, sort: Sort, request: &SolverRequest) -> Result<Term> {
    let t = p.take()?;
    let constant = match (sort, t.text) {
        (Sort::Bool, "true") => Some(ModelValue::Bool(true)),
        (Sort::Bool, "false") => Some(ModelValue::Bool(false)),
        (Sort::Int, "(") => {
            p.expect("-")?;
            let n = p.take()?;
            p.numeral(n, true)?;
            p.expect(")")?;
            p.budget.charge(
                SolverResource::ValueCells,
                n.text
                    .len()
                    .checked_add(1)
                    .and_then(|n| n.checked_mul(2))
                    .ok_or_else(|| p.budget.error(SolverResource::ValueCells))?,
            )?;
            Some(ModelValue::Int(
                Integer::parse(&format!("-{}", n.text)).expect("checked numeral"),
            ))
        }
        (Sort::Int, v) if v.as_bytes().first().is_some_and(u8::is_ascii_digit) => {
            p.numeral(t, false)?;
            p.budget.charge(SolverResource::ValueCells, v.len())?;
            Some(ModelValue::Int(Integer::parse(v).expect("checked numeral")))
        }
        (Sort::Text, "(") => {
            p.expect("as")?;
            let atom = p.take()?;
            let v = p.atom(atom)?;
            p.expect("Text")?;
            p.expect(")")?;
            Some(ModelValue::Text(v))
        }
        (Sort::Text, v) if v.starts_with("@Text_") => Some(ModelValue::Text(p.atom(t)?)),
        _ => None,
    };
    p.budget.charge(SolverResource::ValueCells, 1)?;
    if let Some(v) = constant {
        return Ok(Term::Value(Arc::new(v)));
    }
    if request.catalogue.get(t.text) != Some(&sort) {
        return Err(p.error(t.offset, "unknown-or-wrong-sort-value"));
    }
    p.budget.charge(SolverResource::AliasEdges, 1)?;
    Ok(Term::Alias(p.budget.copy(t.text)?))
}
fn model(p: &mut Parser<'_, '_>, request: &SolverRequest) -> Result<BTreeMap<String, Definition>> {
    p.expect("(")?;
    let mut definitions = BTreeMap::new();
    while p.peek()?.is_some_and(|t| t.text != ")") {
        p.budget.charge(SolverResource::Definitions, 1)?;
        p.budget.charge(SolverResource::ValueCells, 1)?;
        p.expect("(")?;
        p.expect("define-fun")?;
        let name = p.take()?;
        let Some(&expected) = request.catalogue.get(name.text) else {
            return Err(p.error(name.offset, "unknown-definition"));
        };
        if definitions.contains_key(name.text) {
            return Err(p.error(name.offset, "duplicate-definition"));
        }
        p.expect("(")?;
        p.expect(")")?;
        let sort = p.take()?;
        if sort.text != expected.name() {
            return Err(p.error(sort.offset, "definition-sort-mismatch"));
        }
        let term = value(p, expected, request)?;
        p.expect(")")?;
        definitions.insert(
            p.budget.copy(name.text)?,
            Definition {
                sort: expected,
                term,
                offset: name.offset,
            },
        );
    }
    p.expect(")")?;
    Ok(definitions)
}
fn resolve(
    defs: &BTreeMap<String, Definition>,
    b: &mut Budget,
    status: SolverStatus,
) -> Result<BTreeMap<String, Arc<ModelValue>>> {
    let mut values: BTreeMap<String, Arc<ModelValue>> = BTreeMap::new();
    for name in defs.keys() {
        if values.contains_key(name) {
            continue;
        }
        let mut path = Vec::new();
        let mut active = BTreeSet::new();
        let mut at = name.as_str();
        let terminal = loop {
            b.step()?;
            if let Some(v) = values.get(at) {
                break v.clone();
            }
            let d = defs.get(at).ok_or(SolverError::Model {
                offset: defs[name].offset,
                reason: "missing-alias-definition",
                reported_status: status,
                symbol: at.to_owned(),
            })?;
            b.charge(SolverResource::ValueCells, 2)?;
            if !active.insert(at) {
                return Err(SolverError::Model {
                    offset: d.offset,
                    reason: "alias-cycle",
                    reported_status: status,
                    symbol: at.to_owned(),
                });
            }
            path.push(at);
            match &d.term {
                Term::Value(v) => break v.clone(),
                Term::Alias(next) => {
                    if let Some(target) = defs.get(next)
                        && target.sort != d.sort
                    {
                        return Err(SolverError::Model {
                            offset: d.offset,
                            reason: "alias-sort-mismatch",
                            reported_status: status,
                            symbol: at.to_owned(),
                        });
                    }
                    at = next;
                }
            }
        };
        for name in path {
            b.step()?;
            b.charge(SolverResource::ValueCells, 1)?;
            values.insert(b.copy(name)?, terminal.clone());
        }
    }
    Ok(values)
}
fn record(
    request: &SolverRequest,
    input: &SolverResponseInput<'_>,
    b: &mut Budget,
) -> Result<Arc<ResponseRecord>> {
    let stream = |bytes: &[u8], complete| {
        obj(vec![
            ("raw_digest", s(raw_digest(bytes))),
            ("byte_length", s(bytes.len().to_string())),
            ("complete", Value::Bool(complete)),
        ])
    };
    let exit = match input.exit {
        ProcessExit::Exited(n) => obj(vec![("kind", s("exited")), ("code", s(n.to_string()))]),
        ProcessExit::Signaled(n) => obj(vec![("kind", s("signaled")), ("code", s(n.to_string()))]),
        ProcessExit::Unavailable => obj(vec![("kind", s("unavailable"))]),
    };
    let v = obj(vec![
        ("format", s("axiom-p4-solver-response-observation")),
        ("version", s("0.1")),
        ("request", s(request.artifact_digest())),
        ("stdout", stream(input.stdout, input.stdout_complete)),
        ("stderr", stream(input.stderr, input.stderr_complete)),
        ("exit", exit),
        ("outer_termination", s(input.outer_termination.name())),
    ]);
    let bytes = encoding::canonical(&v, SolverResource::ResponseBytes, b)?;
    Ok(Arc::new(ResponseRecord {
        digest: raw_digest(&bytes),
        bytes,
        request: request.artifact_digest().into(),
    }))
}
pub(super) fn parse(
    request: &SolverRequest,
    input: SolverResponseInput<'_>,
) -> Result<SolverResponse> {
    if input.request_digest != request.artifact_digest() {
        return Err(SolverError::BindingMismatch);
    }
    let mut b = Budget::new(request.limits, SolverStage::Response);
    let summary = TransportSummary {
        exit: input.exit,
        outer_termination: input.outer_termination,
        stdout_complete: input.stdout_complete,
        stderr_complete: input.stderr_complete,
        stdout_bytes: input.stdout.len(),
        stderr_bytes: input.stderr.len(),
        stdout_exceeded: input.stdout.len() > request.limits.maximum(SolverResource::StdoutBytes),
        stderr_exceeded: input.stderr.len() > request.limits.maximum(SolverResource::StderrBytes),
    };
    if summary.exit != ProcessExit::Exited(0)
        || summary.outer_termination != OuterTermination::None
        || !summary.stdout_complete
        || !summary.stderr_complete
        || summary.stdout_exceeded
        || summary.stderr_exceeded
    {
        return Err(SolverError::Transport(summary));
    }
    b.charge(SolverResource::StdoutBytes, input.stdout.len())?;
    b.charge(SolverResource::StderrBytes, input.stderr.len())?;
    let source = std::str::from_utf8(input.stdout).map_err(|e| SolverError::Protocol {
        offset: e.valid_up_to(),
        reason: "stdout-not-utf8",
        reported_status: None,
    })?;
    std::str::from_utf8(input.stderr).map_err(|e| SolverError::Protocol {
        offset: e.valid_up_to(),
        reason: "stderr-not-utf8",
        reported_status: None,
    })?;
    if let Some(offset) = input
        .stderr
        .iter()
        .position(|&c| (c < 32 && !matches!(c, b'\t' | b'\r' | b'\n')) || c == 127)
    {
        return Err(SolverError::Protocol {
            offset,
            reason: "stderr-control",
            reported_status: None,
        });
    }
    if let Some(offset) = input
        .stdout
        .iter()
        .position(|&c| (c < 32 && !matches!(c, b'\t' | b'\r' | b'\n')) || c == 127)
    {
        return Err(SolverError::Protocol {
            offset,
            reason: "stdout-control",
            reported_status: None,
        });
    }
    let record = record(request, &input, &mut b)?;
    b.charge(SolverResource::TokenBytes, source.len())?;
    let mut p = Parser {
        source,
        at: 0,
        look: None,
        depth: 0,
        status: None,
        budget: &mut b,
    };
    let first = p.take()?;
    let status = match first.text {
        "sat" => SolverStatus::Sat,
        "unsat" => SolverStatus::Unsat,
        "unknown" => SolverStatus::Unknown,
        _ => return Err(p.error(first.offset, "expected-status")),
    };
    p.status = Some(status);
    let present = p.peek()?.is_some();
    let defs = match status {
        SolverStatus::Sat => Some(model(&mut p, request)?),
        SolverStatus::Unknown if present => Some(model(&mut p, request)?),
        _ => None,
    };
    if let Some(t) = p.next()? {
        return Err(p.error(t.offset, "trailing-output"));
    }
    if p.depth != 0 {
        return Err(p.error(source.len(), "unclosed-frame"));
    }
    let values = if let Some(defs) = defs {
        if status == SolverStatus::Sat {
            for sym in request.query.symbols() {
                if !defs.contains_key(sym.name()) {
                    return Err(SolverError::Model {
                        offset: source.len(),
                        reason: "missing-free-symbol",
                        reported_status: status,
                        symbol: sym.name().to_owned(),
                    });
                }
            }
        }
        resolve(&defs, &mut b, status)?
    } else {
        BTreeMap::new()
    };
    let model = if status == SolverStatus::Sat {
        Some(SatModel {
            record: record.clone(),
            values,
            usage: b.usage.clone(),
        })
    } else {
        None
    };
    Ok(SolverResponse {
        status,
        record,
        model,
        usage: b.usage,
        model_present: present,
    })
}
