//! 固定记录的定向编码器；规范化复用 IR JSON，不解析第二套 JSON。
use crate::{HostError, HostLimits, Result, checked_size};
use radishaxiom_ir::json::{JsonLimits, canonicalize_json};

pub(crate) struct Writer {
    bytes: Vec<u8>,
    max: usize,
}
impl Writer {
    pub(crate) fn new(max: usize) -> Self {
        Self {
            bytes: Vec::new(),
            max,
        }
    }
    pub(crate) fn raw(&mut self, value: &[u8]) -> Result<()> {
        checked_size(self.bytes.len(), value.len(), self.max, "record_bytes")?;
        self.bytes.extend_from_slice(value);
        Ok(())
    }
    pub(crate) fn string(&mut self, value: &str) -> Result<()> {
        self.raw(b"\"")?;
        for byte in value.bytes() {
            match byte {
                b'"' => self.raw(b"\\\"")?,
                b'\\' => self.raw(b"\\\\")?,
                8 => self.raw(b"\\b")?,
                9 => self.raw(b"\\t")?,
                10 => self.raw(b"\\n")?,
                12 => self.raw(b"\\f")?,
                13 => self.raw(b"\\r")?,
                0..=31 => {
                    self.raw(b"\\u00")?;
                    self.raw(&[HEX[usize::from(byte >> 4)], HEX[usize::from(byte & 15)]])?;
                }
                _ => self.raw(&[byte])?,
            }
        }
        self.raw(b"\"")
    }
    pub(crate) fn key(&mut self, name: &str) -> Result<()> {
        self.string(name)?;
        self.raw(b":")
    }
    pub(crate) fn field(&mut self, name: &str, value: &str) -> Result<()> {
        self.key(name)?;
        self.string(value)
    }
    pub(crate) fn boolean(&mut self, value: bool) -> Result<()> {
        self.raw(if value { b"true" } else { b"false" })
    }
    pub(crate) fn hex(&mut self, value: &[u8]) -> Result<()> {
        let count = value
            .len()
            .checked_mul(2)
            .and_then(|n| n.checked_add(2))
            .ok_or(HostError::ResourceLimit("record_bytes"))?;
        checked_size(self.bytes.len(), count, self.max, "record_bytes")?;
        self.raw(b"\"")?;
        for byte in value {
            self.raw(&[HEX[usize::from(byte >> 4)], HEX[usize::from(byte & 15)]])?;
        }
        self.raw(b"\"")
    }
    pub(crate) fn finish(self, limits: HostLimits) -> Result<Vec<u8>> {
        canonicalize_json(
            &self.bytes,
            JsonLimits {
                max_input_bytes: limits.record_bytes,
                max_values: limits.json_values,
                max_nesting: limits.json_nesting,
            },
        )
        .map_err(HostError::Json)
    }
}
const HEX: &[u8; 16] = b"0123456789abcdef";
