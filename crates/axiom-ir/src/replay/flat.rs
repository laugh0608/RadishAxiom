//! world 与观察的平坦 JSON；字符串词法 / JCS 转义复用现有有界标量路径。
use super::{Budget, JsonLimits, ReplayError, ReplayResource as R, Result, difference};
use crate::json::{self, Value};

pub(super) enum Node {
    String(String),
    Bool(bool),
    Array(Vec<usize>),
    Object(Vec<(String, usize)>),
}
pub(super) struct Json {
    pub nodes: Vec<Node>,
    offsets: Vec<usize>,
}
impl Json {
    pub fn new() -> Self {
        Self {
            nodes: Vec::new(),
            offsets: Vec::new(),
        }
    }
    pub fn push(&mut self, n: Node, b: &mut Budget) -> Result<usize> {
        b.charge(R::ValueCells, 2)?;
        let id = self.nodes.len();
        self.nodes.push(n);
        self.offsets.push(0);
        Ok(id)
    }
    pub fn s(&mut self, s: &str, b: &mut Budget) -> Result<usize> {
        let s = b.copy(s)?;
        self.push(Node::String(s), b)
    }
    pub fn n(&mut self, n: usize, b: &mut Budget) -> Result<usize> {
        b.observe(R::IntegerDigits, n.to_string().len())?;
        self.s(&n.to_string(), b)
    }
    pub fn boolean(&mut self, v: bool, b: &mut Budget) -> Result<usize> {
        self.push(Node::Bool(v), b)
    }
    pub fn arr(&mut self, a: Vec<usize>, b: &mut Budget) -> Result<usize> {
        b.charge(R::ValueCells, a.len())?;
        self.push(Node::Array(a), b)
    }
    pub fn obj(&mut self, fields: Vec<(&str, usize)>, b: &mut Budget) -> Result<usize> {
        b.charge(R::ValueCells, fields.len())?;
        let mut m = fields
            .into_iter()
            .map(|(k, v)| Ok((b.copy(k)?, v)))
            .collect::<Result<Vec<_>>>()?;
        m.sort_by(|(a, _), (c, _)| a.encode_utf16().cmp(c.encode_utf16()));
        self.push(Node::Object(m), b)
    }
    pub fn str_object(&mut self, m: &[(&str, &str)], b: &mut Budget) -> Result<usize> {
        b.charge(R::ValueCells, m.len())?;
        let m = m
            .iter()
            .map(|&(k, s)| Ok((k, self.s(s, b)?)))
            .collect::<Result<Vec<_>>>()?;
        self.obj(m, b)
    }
    pub fn error(&self, id: usize, reason: &'static str) -> ReplayError {
        ReplayError::WorldFormat {
            offset: self.offsets[id],
            reason,
        }
    }
    pub fn str(&self, id: usize) -> Result<&str> {
        if let Node::String(s) = &self.nodes[id] {
            Ok(s)
        } else {
            Err(self.error(id, "expected string"))
        }
    }
    pub fn array(&self, id: usize) -> Result<&[usize]> {
        if let Node::Array(a) = &self.nodes[id] {
            Ok(a)
        } else {
            Err(self.error(id, "expected array"))
        }
    }
    pub fn closed(&self, id: usize, keys: &[&str]) -> Result<()> {
        let Node::Object(m) = &self.nodes[id] else {
            return Err(self.error(id, "expected object"));
        };
        if m.len() != keys.len() || m.iter().any(|(k, _)| !keys.contains(&k.as_str())) {
            return Err(self.error(id, "closed members"));
        }
        Ok(())
    }
    pub fn get(&self, id: usize, key: &str) -> Result<usize> {
        let Node::Object(m) = &self.nodes[id] else {
            return Err(self.error(id, "expected object"));
        };
        m.iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| *v)
            .ok_or_else(|| self.error(id, "missing member"))
    }
    pub fn text(&self, id: usize, key: &str) -> Result<&str> {
        self.str(self.get(id, key)?)
    }
    pub fn exact(&self, id: usize, key: &str, value: &str) -> Result<()> {
        if self.text(id, key)? != value {
            Err(self.error(id, "type or tag mismatch"))
        } else {
            Ok(())
        }
    }
    pub fn parse(bytes: &[u8], b: &mut Budget) -> Result<(Self, usize)> {
        enum Frame {
            Array(Vec<usize>),
            Object(Vec<(String, usize)>),
        }
        enum Task {
            Value,
            ArrayNext,
            ObjectKey,
            ObjectNext(String),
        }
        let mut p = Parser { bytes, at: 0 };
        std::str::from_utf8(bytes).map_err(|e| ReplayError::WorldFormat {
            offset: e.valid_up_to(),
            reason: "UTF-8",
        })?;
        let mut out = Self::new();
        let mut frames = Vec::new();
        let mut tasks = vec![Task::Value];
        let mut values = Vec::new();
        b.charge(R::ValueCells, 1)?;
        while let Some(task) = tasks.pop() {
            b.step()?;
            match task {
                Task::Value => {
                    b.charge(R::WorldNodes, 1)?;
                    let start = p.at;
                    let node = match p.peek() {
                        Some(b'"') => Some(Node::String(p.string(b)?)),
                        Some(b't') => {
                            p.expect_word(b"true")?;
                            Some(Node::Bool(true))
                        }
                        Some(b'f') => {
                            p.expect_word(b"false")?;
                            Some(Node::Bool(false))
                        }
                        Some(c @ (b'[' | b'{')) => {
                            p.at += 1;
                            b.observe(R::WorldDepth, frames.len() + 1)?;
                            b.charge(R::ValueCells, 3)?;
                            if c == b'[' {
                                if p.peek() == Some(b']') {
                                    p.at += 1;
                                    Some(Node::Array(Vec::new()))
                                } else {
                                    frames.push(Frame::Array(Vec::new()));
                                    tasks.push(Task::ArrayNext);
                                    tasks.push(Task::Value);
                                    None
                                }
                            } else if p.peek() == Some(b'}') {
                                p.at += 1;
                                Some(Node::Object(Vec::new()))
                            } else {
                                frames.push(Frame::Object(Vec::new()));
                                tasks.push(Task::ObjectKey);
                                None
                            }
                        }
                        _ => return Err(p.error("JSON value")),
                    };
                    if let Some(node) = node {
                        let id = out.push(node, b)?;
                        out.offsets[id] = start;
                        b.charge(R::ValueCells, 1)?;
                        values.push(id);
                    }
                }
                Task::ArrayNext => {
                    let child = values.pop().ok_or(ReplayError::Internal("array child"))?;
                    let Some(Frame::Array(a)) = frames.last_mut() else {
                        return Err(p.error("array frame"));
                    };
                    b.charge(R::ValueCells, 1)?;
                    a.push(child);
                    match p.peek() {
                        Some(b',') => {
                            p.at += 1;
                            b.charge(R::ValueCells, 2)?;
                            tasks.push(Task::ArrayNext);
                            tasks.push(Task::Value);
                        }
                        Some(b']') => {
                            p.at += 1;
                            let Some(Frame::Array(a)) = frames.pop() else {
                                unreachable!()
                            };
                            let id = out.push(Node::Array(a), b)?;
                            values.push(id);
                        }
                        _ => return Err(p.error("array delimiter")),
                    }
                }
                Task::ObjectKey => {
                    b.charge(R::WorldNodes, 1)?;
                    let key = p.string(b)?;
                    let Some(Frame::Object(m)) = frames.last() else {
                        return Err(p.error("object frame"));
                    };
                    if m.last().is_some_and(|(last, _)| {
                        last.encode_utf16().cmp(key.encode_utf16()) != std::cmp::Ordering::Less
                    }) {
                        return Err(p.error("duplicate or noncanonical object key"));
                    }
                    p.expect(b':')?;
                    b.charge(R::ValueCells, 2)?;
                    tasks.push(Task::ObjectNext(key));
                    tasks.push(Task::Value);
                }
                Task::ObjectNext(key) => {
                    let child = values.pop().ok_or(ReplayError::Internal("object child"))?;
                    let Some(Frame::Object(m)) = frames.last_mut() else {
                        return Err(p.error("object frame"));
                    };
                    b.charge(R::ValueCells, 1)?;
                    m.push((key, child));
                    match p.peek() {
                        Some(b',') => {
                            p.at += 1;
                            b.charge(R::ValueCells, 1)?;
                            tasks.push(Task::ObjectKey);
                        }
                        Some(b'}') => {
                            p.at += 1;
                            let Some(Frame::Object(m)) = frames.pop() else {
                                unreachable!()
                            };
                            let id = out.push(Node::Object(m), b)?;
                            values.push(id);
                        }
                        _ => return Err(p.error("object delimiter")),
                    }
                }
            }
        }
        if p.at != bytes.len() || values.len() != 1 {
            return Err(p.error("trailing bytes"));
        }
        let root = values[0];
        // 每个 token 已验证最小转义、对象键序与无空白；容器只有平坦索引。
        Ok((out, root))
    }
    pub fn tape(&self, root: usize, b: &mut Budget) -> Result<Vec<Part>> {
        enum Task {
            Node(usize),
            Part(Part),
        }
        b.charge(R::ValueCells, 1)?;
        let mut stack = vec![Task::Node(root)];
        let mut parts = Vec::new();
        while let Some(task) = stack.pop() {
            b.step()?;
            let part = match task {
                Task::Part(p) => p,
                Task::Node(id) => match &self.nodes[id] {
                    Node::String(_) | Node::Bool(_) => Part::Scalar(id),
                    Node::Array(a) => {
                        let count = a
                            .len()
                            .checked_mul(2)
                            .map(|n| n.max(1))
                            .ok_or_else(|| b.error(R::ValueCells))?;
                        b.charge(R::ValueCells, count)?;
                        stack.push(Task::Part(Part::Raw(b"]")));
                        for (i, &id) in a.iter().enumerate().rev() {
                            stack.push(Task::Node(id));
                            if i > 0 {
                                stack.push(Task::Part(Part::Raw(b",")));
                            }
                        }
                        Part::Raw(b"[")
                    }
                    Node::Object(m) => {
                        let count = m
                            .len()
                            .checked_mul(4)
                            .map(|n| n.max(1))
                            .ok_or_else(|| b.error(R::ValueCells))?;
                        b.charge(R::ValueCells, count)?;
                        stack.push(Task::Part(Part::Raw(b"}")));
                        for (i, (_, child)) in m.iter().enumerate().rev() {
                            stack.push(Task::Node(*child));
                            stack.push(Task::Part(Part::Raw(b":")));
                            stack.push(Task::Part(Part::Key(id, i)));
                            if i > 0 {
                                stack.push(Task::Part(Part::Raw(b",")));
                            }
                        }
                        Part::Raw(b"{")
                    }
                },
            };
            b.charge(R::ValueCells, 1)?;
            parts.push(part);
        }
        Ok(parts)
    }
    pub fn emit_tape(&self, parts: &[Part], write: &mut impl FnMut(&[u8])) {
        for part in parts {
            match part {
                Part::Raw(bytes) => write(bytes),
                Part::Key(id, index) => {
                    let Node::Object(m) = &self.nodes[*id] else {
                        unreachable!()
                    };
                    json::emit_string(&m[*index].0, write);
                }
                Part::Scalar(id) => match &self.nodes[*id] {
                    Node::String(s) => json::emit_string(s, write),
                    Node::Bool(v) => write(if *v { b"true" } else { b"false" }),
                    _ => unreachable!(),
                },
            }
        }
    }
    pub fn tape_length(&self, parts: &[Part]) -> Result<usize> {
        let mut length = Some(0usize);
        self.emit_tape(parts, &mut |s| {
            length = length.and_then(|n| n.checked_add(s.len()))
        });
        length.ok_or(ReplayError::ResourceLimit {
            stage: super::ReplayStage::Output,
            resource: R::OutputBytes,
        })
    }
    pub fn encode_tape(&self, parts: &[Part], length: usize) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(length);
        self.emit_tape(parts, &mut |s| bytes.extend_from_slice(s));
        bytes
    }
}
pub(super) enum Part {
    Raw(&'static [u8]),
    Scalar(usize),
    Key(usize, usize),
}
struct Parser<'a> {
    bytes: &'a [u8],
    at: usize,
}
impl Parser<'_> {
    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.at).copied()
    }
    fn error(&self, reason: &'static str) -> ReplayError {
        ReplayError::WorldFormat {
            offset: self.at,
            reason,
        }
    }
    fn expect(&mut self, c: u8) -> Result<()> {
        if self.peek() != Some(c) {
            return Err(self.error("delimiter"));
        }
        self.at += 1;
        Ok(())
    }
    fn expect_word(&mut self, w: &[u8]) -> Result<()> {
        if self.bytes.get(self.at..self.at + w.len()) != Some(w) {
            return Err(self.error("boolean"));
        }
        self.at += w.len();
        Ok(())
    }
    fn string(&mut self, b: &mut Budget) -> Result<String> {
        let start = self.at;
        self.expect(b'"')?;
        let mut escaped = false;
        loop {
            let c = self.peek().ok_or_else(|| self.error("string EOF"))?;
            self.at += 1;
            if c == b'"' && !escaped {
                break;
            }
            escaped = c == b'\\' && !escaped;
        }
        let token = &self.bytes[start..self.at];
        b.charge(
            R::ValueCells,
            token
                .len()
                .checked_mul(2)
                .ok_or_else(|| b.error(R::ValueCells))?,
        )?;
        let v = json::parse(
            token,
            JsonLimits {
                max_input_bytes: token.len(),
                max_values: 1,
                max_nesting: 0,
            },
        )
        .map_err(|_| self.error("string Unicode or escape"))?;
        let Value::String(s) = v else { unreachable!() };
        let mut canonical = Vec::new();
        json::encode_string(&s, &mut canonical);
        if token != canonical {
            return Err(ReplayError::NonCanonicalWorld {
                offset: start + difference(token, &canonical),
            });
        }
        Ok(s)
    }
}
