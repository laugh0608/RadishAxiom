use std::error::Error;
use std::fmt;

use crate::sha256;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DocumentError {
    code: &'static str,
    path: String,
}

impl DocumentError {
    pub(crate) fn new(code: &'static str, path: impl Into<String>) -> Self {
        Self {
            code,
            path: path.into(),
        }
    }

    pub fn code(&self) -> &'static str {
        self.code
    }

    pub fn path(&self) -> &str {
        &self.path
    }
}

impl fmt::Display for DocumentError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}: {}", self.code, self.path)
    }
}

impl Error for DocumentError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) enum Value {
    String(String),
    Bool(bool),
    Array(Vec<Value>),
    Object(Vec<(String, Value)>),
}

pub(crate) struct ShapeSpec<'a> {
    pub object_fields: &'a [(&'a str, &'a str)],
    pub array_paths: &'a [&'a str],
    pub bool_paths: &'a [&'a str],
}

pub(crate) fn parse(data: &[u8], require_compact: bool) -> Result<Value, DocumentError> {
    let mut parser = Parser { data, offset: 0 };
    let value = parser.parse_value()?;
    parser.skip_whitespace();
    if parser.offset != data.len() {
        return Err(parser.error("trailing-json"));
    }
    if require_compact && canonical_bytes(&value) != data {
        return Err(DocumentError::new("noncanonical-json", "$"));
    }
    Ok(value)
}

pub(crate) fn canonical_bytes(value: &Value) -> Vec<u8> {
    let mut output = Vec::new();
    encode(value, &mut output);
    output
}

pub(crate) fn domain_digest(
    domain: &str,
    value: &Value,
    digest_field: &str,
) -> Result<String, DocumentError> {
    let object = as_object(value, "$")?;
    if !object.iter().any(|(key, _)| key == digest_field) {
        return Err(DocumentError::new(
            "missing-member",
            format!("$.{digest_field}"),
        ));
    }
    let body = Value::Object(
        object
            .iter()
            .filter(|(key, _)| key != digest_field)
            .cloned()
            .collect(),
    );
    Ok(domain_digest_value(domain, &body))
}

pub(crate) fn domain_digest_value(domain: &str, value: &Value) -> String {
    let canonical = canonical_bytes(value);
    let mut input = Vec::with_capacity(domain.len() + 1 + canonical.len());
    input.extend_from_slice(domain.as_bytes());
    input.push(0);
    input.extend_from_slice(&canonical);
    format!("sha256:{}", sha256::digest_hex(&input))
}

pub(crate) fn validate_shape(value: &Value, spec: &ShapeSpec<'_>) -> Result<(), DocumentError> {
    validate_shape_at(value, "$", spec)
}

pub(crate) fn as_object<'a>(
    value: &'a Value,
    path: &str,
) -> Result<&'a [(String, Value)], DocumentError> {
    match value {
        Value::Object(object) => Ok(object),
        _ => Err(DocumentError::new("invalid-object", path)),
    }
}

pub(crate) fn as_array<'a>(value: &'a Value, path: &str) -> Result<&'a [Value], DocumentError> {
    match value {
        Value::Array(array) => Ok(array),
        _ => Err(DocumentError::new("invalid-array", path)),
    }
}

pub(crate) fn as_string<'a>(value: &'a Value, path: &str) -> Result<&'a str, DocumentError> {
    match value {
        Value::String(text) => Ok(text),
        _ => Err(DocumentError::new("invalid-string", path)),
    }
}

pub(crate) fn as_bool(value: &Value, path: &str) -> Result<bool, DocumentError> {
    match value {
        Value::Bool(value) => Ok(*value),
        _ => Err(DocumentError::new("invalid-boolean", path)),
    }
}

pub(crate) fn member<'a>(
    object: &'a [(String, Value)],
    name: &str,
    path: &str,
) -> Result<&'a Value, DocumentError> {
    object
        .binary_search_by(|(key, _)| key.as_str().cmp(name))
        .map(|index| &object[index].1)
        .map_err(|_| DocumentError::new("missing-member", format!("{path}.{name}")))
}

pub(crate) fn string_member<'a>(
    object: &'a [(String, Value)],
    name: &str,
    path: &str,
) -> Result<&'a str, DocumentError> {
    as_string(member(object, name, path)?, &format!("{path}.{name}"))
}

pub(crate) fn bool_member(
    object: &[(String, Value)],
    name: &str,
    path: &str,
) -> Result<bool, DocumentError> {
    as_bool(member(object, name, path)?, &format!("{path}.{name}"))
}

pub(crate) fn validate_digest(text: &str, path: &str) -> Result<(), DocumentError> {
    let Some(hex) = text.strip_prefix("sha256:") else {
        return Err(DocumentError::new("invalid-digest", path));
    };
    if hex.len() != 64
        || !hex
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
    {
        return Err(DocumentError::new("invalid-digest", path));
    }
    Ok(())
}

pub(crate) fn parse_decimal(text: &str, path: &str) -> Result<u64, DocumentError> {
    if text.is_empty()
        || (text.len() > 1 && text.starts_with('0'))
        || !text.bytes().all(|byte| byte.is_ascii_digit())
    {
        return Err(DocumentError::new("invalid-decimal", path));
    }
    text.parse::<u64>()
        .map_err(|_| DocumentError::new("decimal-overflow", path))
}

fn validate_shape_at(value: &Value, path: &str, spec: &ShapeSpec<'_>) -> Result<(), DocumentError> {
    if let Some((_, fields)) = spec
        .object_fields
        .iter()
        .find(|(candidate, _)| *candidate == path)
    {
        let object = as_object(value, path)?;
        let expected: Vec<&str> = fields.split(',').collect();
        for (key, _) in object {
            if expected.binary_search(&key.as_str()).is_err() {
                return Err(DocumentError::new(
                    "unknown-member",
                    format!("{path}.{key}"),
                ));
            }
        }
        for key in &expected {
            if object
                .binary_search_by(|(actual, _)| actual.as_str().cmp(key))
                .is_err()
            {
                return Err(DocumentError::new(
                    "missing-member",
                    format!("{path}.{key}"),
                ));
            }
        }
        for (key, item) in object {
            validate_shape_at(item, &format!("{path}.{key}"), spec)?;
        }
        return Ok(());
    }

    if spec.array_paths.contains(&path) {
        let array = as_array(value, path)?;
        for item in array {
            validate_shape_at(item, &format!("{path}[]"), spec)?;
        }
        return Ok(());
    }

    if spec.bool_paths.contains(&path) {
        return match value {
            Value::Bool(_) => Ok(()),
            _ => Err(DocumentError::new("invalid-boolean", path)),
        };
    }

    match value {
        Value::String(_) => Ok(()),
        Value::Bool(_) => Err(DocumentError::new("unexpected-boolean", path)),
        Value::Array(_) => Err(DocumentError::new("unexpected-array", path)),
        Value::Object(_) => Err(DocumentError::new("unexpected-object", path)),
    }
}

fn encode(value: &Value, output: &mut Vec<u8>) {
    match value {
        Value::String(text) => encode_string(text, output),
        Value::Bool(true) => output.extend_from_slice(b"true"),
        Value::Bool(false) => output.extend_from_slice(b"false"),
        Value::Array(array) => {
            output.push(b'[');
            for (index, item) in array.iter().enumerate() {
                if index > 0 {
                    output.push(b',');
                }
                encode(item, output);
            }
            output.push(b']');
        }
        Value::Object(object) => {
            output.push(b'{');
            for (index, (key, item)) in object.iter().enumerate() {
                if index > 0 {
                    output.push(b',');
                }
                encode_string(key, output);
                output.push(b':');
                encode(item, output);
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
            0x08 => output.extend_from_slice(b"\\b"),
            0x09 => output.extend_from_slice(b"\\t"),
            0x0a => output.extend_from_slice(b"\\n"),
            0x0c => output.extend_from_slice(b"\\f"),
            0x0d => output.extend_from_slice(b"\\r"),
            0x00..=0x1f => {
                const HEX: &[u8; 16] = b"0123456789abcdef";
                output.extend_from_slice(b"\\u00");
                output.push(HEX[usize::from(byte >> 4)]);
                output.push(HEX[usize::from(byte & 0x0f)]);
            }
            _ => output.push(byte),
        }
    }
    output.push(b'"');
}

struct Parser<'a> {
    data: &'a [u8],
    offset: usize,
}

impl Parser<'_> {
    fn parse_value(&mut self) -> Result<Value, DocumentError> {
        self.skip_whitespace();
        match self.peek() {
            Some(b'"') => self.parse_string().map(Value::String),
            Some(b'{') => self.parse_object(),
            Some(b'[') => self.parse_array(),
            Some(b't') => {
                self.consume_token(b"true")?;
                Ok(Value::Bool(true))
            }
            Some(b'f') => {
                self.consume_token(b"false")?;
                Ok(Value::Bool(false))
            }
            Some(_) => Err(self.error("number-null-or-unsupported-json")),
            None => Err(self.error("unexpected-eof")),
        }
    }

    fn parse_object(&mut self) -> Result<Value, DocumentError> {
        self.expect(b'{')?;
        self.skip_whitespace();
        let mut object = Vec::new();
        if self.take_if(b'}') {
            return Ok(Value::Object(object));
        }
        loop {
            self.skip_whitespace();
            let key = self.parse_string()?;
            if let Some((previous, _)) = object.last() {
                match previous.cmp(&key) {
                    std::cmp::Ordering::Equal => return Err(self.error("duplicate-member")),
                    std::cmp::Ordering::Greater => {
                        return Err(self.error("noncanonical-member-order"));
                    }
                    std::cmp::Ordering::Less => {}
                }
            }
            self.skip_whitespace();
            self.expect(b':')?;
            let value = self.parse_value()?;
            object.push((key, value));
            self.skip_whitespace();
            if self.take_if(b'}') {
                break;
            }
            self.expect(b',')?;
        }
        Ok(Value::Object(object))
    }

    fn parse_array(&mut self) -> Result<Value, DocumentError> {
        self.expect(b'[')?;
        self.skip_whitespace();
        let mut array = Vec::new();
        if self.take_if(b']') {
            return Ok(Value::Array(array));
        }
        loop {
            array.push(self.parse_value()?);
            self.skip_whitespace();
            if self.take_if(b']') {
                break;
            }
            self.expect(b',')?;
        }
        Ok(Value::Array(array))
    }

    fn parse_string(&mut self) -> Result<String, DocumentError> {
        self.expect(b'"')?;
        let mut output = String::new();
        loop {
            let Some(byte) = self.next() else {
                return Err(self.error("unterminated-string"));
            };
            match byte {
                b'"' => return Ok(output),
                b'\\' => self.parse_escape(&mut output)?,
                0x20..=0x7e => output.push(char::from(byte)),
                0x00..=0x1f => return Err(self.error("unescaped-control")),
                _ => return Err(self.error("non-ascii-string")),
            }
        }
    }

    fn parse_escape(&mut self, output: &mut String) -> Result<(), DocumentError> {
        let Some(escape) = self.next() else {
            return Err(self.error("unterminated-escape"));
        };
        match escape {
            b'"' => output.push('"'),
            b'\\' => output.push('\\'),
            b'b' => output.push('\u{0008}'),
            b't' => output.push('\t'),
            b'n' => output.push('\n'),
            b'f' => output.push('\u{000c}'),
            b'r' => output.push('\r'),
            b'u' => {
                let code = self.parse_hex_quad()?;
                if code > 0x1f || matches!(code, 0x08 | 0x09 | 0x0a | 0x0c | 0x0d) {
                    return Err(self.error("noncanonical-escape"));
                }
                output.push(char::from(code as u8));
            }
            _ => return Err(self.error("noncanonical-escape")),
        }
        Ok(())
    }

    fn parse_hex_quad(&mut self) -> Result<u16, DocumentError> {
        let mut value = 0_u16;
        for _ in 0..4 {
            let Some(byte) = self.next() else {
                return Err(self.error("unterminated-escape"));
            };
            let digit = match byte {
                b'0'..=b'9' => u16::from(byte - b'0'),
                b'a'..=b'f' => u16::from(byte - b'a' + 10),
                _ => return Err(self.error("noncanonical-escape")),
            };
            value = value * 16 + digit;
        }
        Ok(value)
    }

    fn consume_token(&mut self, token: &[u8]) -> Result<(), DocumentError> {
        if self.data.get(self.offset..self.offset + token.len()) == Some(token) {
            self.offset += token.len();
            Ok(())
        } else {
            Err(self.error("invalid-json-token"))
        }
    }

    fn expect(&mut self, expected: u8) -> Result<(), DocumentError> {
        match self.next() {
            Some(actual) if actual == expected => Ok(()),
            _ => Err(self.error("invalid-json-syntax")),
        }
    }

    fn take_if(&mut self, expected: u8) -> bool {
        if self.peek() == Some(expected) {
            self.offset += 1;
            true
        } else {
            false
        }
    }

    fn skip_whitespace(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.offset += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.data.get(self.offset).copied()
    }

    fn next(&mut self) -> Option<u8> {
        let byte = self.peek()?;
        self.offset += 1;
        Some(byte)
    }

    fn error(&self, code: &'static str) -> DocumentError {
        DocumentError::new(code, format!("byte {}", self.offset))
    }
}

#[cfg(test)]
mod tests {
    use super::{Value, canonical_bytes, parse};

    #[test]
    fn parser_accepts_only_sorted_closed_ascii_subset() {
        let value = parse(br#"{"a":["x",true],"b":"\u0000"}"#, true).unwrap();
        assert_eq!(canonical_bytes(&value), br#"{"a":["x",true],"b":"\u0000"}"#);
        assert_eq!(
            value,
            Value::Object(vec![
                (
                    "a".into(),
                    Value::Array(vec![Value::String("x".into()), Value::Bool(true)]),
                ),
                ("b".into(), Value::String("\0".into())),
            ])
        );
    }

    #[test]
    fn parser_rejects_duplicate_unsorted_and_noncanonical_forms() {
        for (data, code) in [
            (&br#"{"a":"x","a":"y"}"#[..], "duplicate-member"),
            (&br#"{"b":"x","a":"y"}"#[..], "noncanonical-member-order"),
            (&br#"{"a":"\/"}"#[..], "noncanonical-escape"),
            (&br#"{"a":null}"#[..], "number-null-or-unsupported-json"),
            (&br#"{"a":1}"#[..], "number-null-or-unsupported-json"),
            (&b"{\"a\":\"\xc3\xa9\"}"[..], "non-ascii-string"),
            (&br#"{ "a":"x"}"#[..], "noncanonical-json"),
        ] {
            assert_eq!(parse(data, true).unwrap_err().code(), code);
        }
    }
}
