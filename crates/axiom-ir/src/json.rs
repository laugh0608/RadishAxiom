//! IR v0.1 使用的无 number / null JSON 子集。成功仅表示 JSON 层合法；
//! 类型、名称、数学整数、闭合成员、DAG 与内容身份由后续 IR 层检查。

use std::fmt;

/// 限制递归解析、编码及销毁的栈深度，与 IR 的语义深度无关。
pub const MAX_NESTING: usize = 128;

/// 调用方必须显式提供预算。输入字节还约束字符串总量与输出字节量；
/// 此子集的规范编码不会比合法输入更长。对象成员名也计入 value 预算。
#[derive(Clone, Copy, Debug)]
pub struct JsonLimits {
    pub max_input_bytes: usize,
    pub max_values: usize,
    /// 实际上限为此值与 MAX_NESTING 的较小者，标量不消耗嵌套层数。
    pub max_nesting: usize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ResourceLimit {
    InputBytes,
    Values,
    Nesting,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum JsonErrorKind {
    InvalidUtf8,
    UnexpectedEnd,
    UnexpectedToken,
    TrailingData,
    InvalidEscape,
    UnescapedControl,
    UnpairedSurrogate,
    DuplicateKey,
    NumberOrNull,
    ResourceLimit(ResourceLimit),
}

/// offset 是原输入的零基 UTF-8 字节位置；EOF 使用 input.len()。
/// 预算错误只表示本次未处理完毕，不能解释为输入违反 IR 规范。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct JsonError {
    pub kind: JsonErrorKind,
    pub offset: usize,
}

impl fmt::Display for JsonError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "JSON {:?} at byte {}", self.kind, self.offset)
    }
}

impl std::error::Error for JsonError {}

#[derive(Debug)]
enum Value {
    String(String),
    Bool(bool),
    Array(Vec<Value>),
    Object(Vec<(String, Value, usize)>),
}

/// 解析完整输入，拒绝重复解码键及非法 Unicode，按 UTF-16 排序对象键，
/// 返回无 BOM / 空白 / 末尾换行的规范 UTF-8。数组与字符串内容保持原样。
/// 这不是通用 JCS 实现，也不是完整 IR validator；不生成 digest 或 Evidence。
pub fn canonicalize_json(input: &[u8], limits: JsonLimits) -> Result<Vec<u8>, JsonError> {
    if input.len() > limits.max_input_bytes {
        return Err(JsonError {
            kind: JsonErrorKind::ResourceLimit(ResourceLimit::InputBytes),
            offset: limits.max_input_bytes,
        });
    }
    let text = std::str::from_utf8(input).map_err(|error| JsonError {
        kind: JsonErrorKind::InvalidUtf8,
        offset: error.valid_up_to(),
    })?;
    let mut parser = Parser {
        text,
        offset: 0,
        values: 0,
        limits,
    };
    let value = parser.value(0)?;
    parser.whitespace();
    if parser.offset != input.len() {
        return Err(parser.error(JsonErrorKind::TrailingData));
    }
    let mut output = Vec::with_capacity(input.len());
    encode(&value, &mut output);
    Ok(output)
}

struct Parser<'a> {
    text: &'a str,
    offset: usize,
    values: usize,
    limits: JsonLimits,
}

impl Parser<'_> {
    fn error(&self, kind: JsonErrorKind) -> JsonError {
        JsonError {
            kind,
            offset: self.offset,
        }
    }

    fn peek(&self) -> Option<u8> {
        self.text.as_bytes().get(self.offset).copied()
    }

    fn whitespace(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\r' | b'\n')) {
            self.offset += 1;
        }
    }

    fn expect(&mut self, byte: u8) -> Result<(), JsonError> {
        match self.peek() {
            Some(found) if found == byte => {
                self.offset += 1;
                Ok(())
            }
            Some(_) => Err(self.error(JsonErrorKind::UnexpectedToken)),
            None => Err(self.error(JsonErrorKind::UnexpectedEnd)),
        }
    }

    fn count_value(&mut self) -> Result<(), JsonError> {
        if self.values >= self.limits.max_values {
            return Err(self.error(JsonErrorKind::ResourceLimit(ResourceLimit::Values)));
        }
        self.values += 1;
        Ok(())
    }

    fn value(&mut self, nesting: usize) -> Result<Value, JsonError> {
        self.whitespace();
        self.count_value()?;
        match self.peek() {
            Some(b'"') => Ok(Value::String(self.string()?)),
            Some(b't') => self.literal(b"true", true),
            Some(b'f') => self.literal(b"false", false),
            Some(b'[' | b'{') => {
                if nesting >= self.limits.max_nesting.min(MAX_NESTING) {
                    return Err(self.error(JsonErrorKind::ResourceLimit(ResourceLimit::Nesting)));
                }
                if self.peek() == Some(b'[') {
                    self.array(nesting + 1)
                } else {
                    self.object(nesting + 1)
                }
            }
            Some(b'-' | b'0'..=b'9' | b'n') => Err(self.error(JsonErrorKind::NumberOrNull)),
            Some(_) => Err(self.error(JsonErrorKind::UnexpectedToken)),
            None => Err(self.error(JsonErrorKind::UnexpectedEnd)),
        }
    }

    fn literal(&mut self, bytes: &[u8], value: bool) -> Result<Value, JsonError> {
        for byte in bytes {
            self.expect(*byte)?;
        }
        Ok(Value::Bool(value))
    }

    fn array(&mut self, nesting: usize) -> Result<Value, JsonError> {
        self.expect(b'[')?;
        self.whitespace();
        let mut values = Vec::new();
        if self.peek() != Some(b']') {
            loop {
                values.push(self.value(nesting)?);
                self.whitespace();
                if self.peek() != Some(b',') {
                    break;
                }
                self.offset += 1;
            }
        }
        self.expect(b']')?;
        Ok(Value::Array(values))
    }

    fn object(&mut self, nesting: usize) -> Result<Value, JsonError> {
        self.expect(b'{')?;
        self.whitespace();
        let mut members = Vec::new();
        if self.peek() != Some(b'}') {
            loop {
                self.whitespace();
                let key_offset = self.offset;
                self.count_value()?;
                let key = self.string()?;
                self.whitespace();
                self.expect(b':')?;
                members.push((key, self.value(nesting)?, key_offset));
                self.whitespace();
                if self.peek() != Some(b',') {
                    break;
                }
                self.offset += 1;
            }
        }
        self.expect(b'}')?;
        // Rust str 的顺序是 UTF-8 / scalar 顺序；JCS 要求 UTF-16 code unit 顺序。
        members.sort_by(|a, b| a.0.encode_utf16().cmp(b.0.encode_utf16()));
        for pair in members.windows(2) {
            if pair[0].0 == pair[1].0 {
                return Err(JsonError {
                    kind: JsonErrorKind::DuplicateKey,
                    offset: pair[1].2,
                });
            }
        }
        Ok(Value::Object(members))
    }

    fn string(&mut self) -> Result<String, JsonError> {
        self.expect(b'"')?;
        let mut result = String::new();
        loop {
            match self.peek() {
                Some(b'"') => {
                    self.offset += 1;
                    return Ok(result);
                }
                Some(b'\\') => {
                    self.offset += 1;
                    let escaped = match self.peek() {
                        Some(b'"') => '"',
                        Some(b'\\') => '\\',
                        Some(b'/') => '/',
                        Some(b'b') => '\u{0008}',
                        Some(b'f') => '\u{000c}',
                        Some(b'n') => '\n',
                        Some(b'r') => '\r',
                        Some(b't') => '\t',
                        Some(b'u') => {
                            self.offset += 1;
                            result.push(self.unicode_escape()?);
                            continue;
                        }
                        Some(_) => return Err(self.error(JsonErrorKind::InvalidEscape)),
                        None => return Err(self.error(JsonErrorKind::UnexpectedEnd)),
                    };
                    result.push(escaped);
                    self.offset += 1;
                }
                Some(0..=31) => return Err(self.error(JsonErrorKind::UnescapedControl)),
                Some(_) => {
                    // 输入已通过 UTF-8 校验，正常分支始终位于字符边界。
                    let ch = self.text[self.offset..]
                        .chars()
                        .next()
                        .expect("UTF-8 character");
                    result.push(ch);
                    self.offset += ch.len_utf8();
                }
                None => return Err(self.error(JsonErrorKind::UnexpectedEnd)),
            }
        }
    }

    fn hex_quad(&mut self) -> Result<u32, JsonError> {
        let mut value = 0;
        for _ in 0..4 {
            let digit = match self.peek() {
                Some(byte @ b'0'..=b'9') => byte - b'0',
                Some(byte @ b'a'..=b'f') => byte - b'a' + 10,
                Some(byte @ b'A'..=b'F') => byte - b'A' + 10,
                Some(_) => return Err(self.error(JsonErrorKind::InvalidEscape)),
                None => return Err(self.error(JsonErrorKind::UnexpectedEnd)),
            };
            value = value * 16 + u32::from(digit);
            self.offset += 1;
        }
        Ok(value)
    }

    fn unicode_escape(&mut self) -> Result<char, JsonError> {
        let start = self.offset - 2;
        let first = self.hex_quad()?;
        let scalar = match first {
            0xd800..=0xdbff => {
                if !self.text.as_bytes()[self.offset..].starts_with(b"\\u") {
                    return Err(JsonError {
                        kind: JsonErrorKind::UnpairedSurrogate,
                        offset: start,
                    });
                }
                self.offset += 2;
                let second = self.hex_quad()?;
                if !(0xdc00..=0xdfff).contains(&second) {
                    return Err(JsonError {
                        kind: JsonErrorKind::UnpairedSurrogate,
                        offset: start,
                    });
                }
                0x10000 + ((first - 0xd800) << 10) + second - 0xdc00
            }
            0xdc00..=0xdfff => {
                return Err(JsonError {
                    kind: JsonErrorKind::UnpairedSurrogate,
                    offset: start,
                });
            }
            _ => first,
        };
        Ok(char::from_u32(scalar).expect("validated Unicode scalar"))
    }
}

fn encode(value: &Value, output: &mut Vec<u8>) {
    match value {
        Value::String(text) => encode_string(text, output),
        Value::Bool(true) => output.extend_from_slice(b"true"),
        Value::Bool(false) => output.extend_from_slice(b"false"),
        Value::Array(values) => {
            output.push(b'[');
            for (index, value) in values.iter().enumerate() {
                if index > 0 {
                    output.push(b',');
                }
                encode(value, output);
            }
            output.push(b']');
        }
        Value::Object(members) => {
            output.push(b'{');
            for (index, (key, value, _)) in members.iter().enumerate() {
                if index > 0 {
                    output.push(b',');
                }
                encode_string(key, output);
                output.push(b':');
                encode(value, output);
            }
            output.push(b'}');
        }
    }
}

fn encode_string(text: &str, output: &mut Vec<u8>) {
    output.push(b'"');
    for byte in text.bytes() {
        match byte {
            b'"' => output.extend_from_slice(b"\\\""),
            b'\\' => output.extend_from_slice(b"\\\\"),
            8 => output.extend_from_slice(b"\\b"),
            9 => output.extend_from_slice(b"\\t"),
            10 => output.extend_from_slice(b"\\n"),
            12 => output.extend_from_slice(b"\\f"),
            13 => output.extend_from_slice(b"\\r"),
            0..=31 => {
                output.extend_from_slice(b"\\u00");
                output.push(b"0123456789abcdef"[usize::from(byte >> 4)]);
                output.push(b"0123456789abcdef"[usize::from(byte & 15)]);
            }
            _ => output.push(byte),
        }
    }
    output.push(b'"');
}
