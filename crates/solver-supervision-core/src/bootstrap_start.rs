//! Closed startup declarations, not authenticated runtime observations.
use crate::wire::{BootstrapBinding, WireLimits};
use std::fmt;

pub const START_FORMAT: &str = "solver-bootstrap-start-v0.1";
pub const START_BYTES_MAX: usize = 4096;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StartFields {
    pub attempt: [u8; 32],
    pub request: [u8; 32],
    pub query_bytes: u32,
    pub query_digest: [u8; 32],
    pub policy_bundle: [u8; 32],
    pub image: [u8; 32],
    pub cli_acceptance: [u8; 32],
    pub configuration: [u8; 32],
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StartDescription {
    fields: StartFields,
}
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum StartError {
    Length { actual: usize, maximum: usize },
    NonAscii { offset: usize },
    Syntax { field: &'static str, offset: usize },
    Hex { field: &'static str, offset: usize },
    Integer { field: &'static str, offset: usize },
    QueryLength { actual: usize, maximum: usize },
    QueryDigest,
    NonCanonical { offset: usize },
}
impl fmt::Display for StartError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "bootstrap start declaration: {self:?}")
    }
}
impl std::error::Error for StartError {}

impl StartDescription {
    pub fn new(fields: StartFields, limits: WireLimits) -> Result<Self, StartError> {
        if fields.query_bytes == 0 || fields.query_bytes as usize > limits.query_bytes {
            return Err(StartError::QueryLength {
                actual: fields.query_bytes as usize,
                maximum: limits.query_bytes,
            });
        }
        Ok(Self { fields })
    }
    pub fn fields(&self) -> &StartFields {
        &self.fields
    }
    pub fn scope(&self) -> &'static str {
        "external-declarations-only"
    }
    pub fn binding(&self, declared_nonce: [u8; 32]) -> BootstrapBinding {
        BootstrapBinding {
            attempt: self.fields.attempt,
            request: self.fields.request,
            policy: self.fields.policy_bundle,
            image: self.fields.image,
            nonce: declared_nonce,
        }
    }
    pub fn validate_query(&self, bytes: &[u8]) -> Result<(), StartError> {
        // Reject length before hashing; the description was already bounded.
        if bytes.len() != self.fields.query_bytes as usize {
            return Err(StartError::QueryLength {
                actual: bytes.len(),
                maximum: self.fields.query_bytes as usize,
            });
        }
        if radishaxiom_digest::digest(bytes) != self.fields.query_digest {
            return Err(StartError::QueryDigest);
        }
        Ok(())
    }
    pub fn canonical_bytes(&self) -> Vec<u8> {
        let f = &self.fields;
        let mut out = format!("{{\"format\":\"{START_FORMAT}\",\"attempt\":\"");
        append_hex(&mut out, &f.attempt);
        out.push_str("\",\"request\":\"sha256:");
        append_hex(&mut out, &f.request);
        out.push_str(&format!(
            "\",\"query_bytes\":{},\"query_digest\":\"sha256:",
            f.query_bytes
        ));
        append_hex(&mut out, &f.query_digest);
        for (name, value) in [
            ("policy_bundle", f.policy_bundle),
            ("image", f.image),
            ("cli_acceptance", f.cli_acceptance),
            ("configuration", f.configuration),
        ] {
            out.push_str("\",\"");
            out.push_str(name);
            out.push_str("\":\"sha256:");
            append_hex(&mut out, &value);
        }
        out.push_str("\"}");
        out.into_bytes()
    }
    pub fn parse(bytes: &[u8], limits: WireLimits) -> Result<Self, StartError> {
        if bytes.len() > START_BYTES_MAX {
            return Err(StartError::Length {
                actual: bytes.len(),
                maximum: START_BYTES_MAX,
            });
        }
        if let Some(offset) = bytes.iter().position(|b| !b.is_ascii()) {
            return Err(StartError::NonAscii { offset });
        }
        let mut p = Parser { bytes, at: 0 };
        p.literal(
            b"{\"format\":\"solver-bootstrap-start-v0.1\",\"attempt\":\"",
            "format",
        )?;
        let attempt = p.hex("attempt")?;
        p.literal(b"\",\"request\":\"sha256:", "request")?;
        let request = p.hex("request")?;
        p.literal(b"\",\"query_bytes\":", "query_bytes")?;
        let query_bytes = p.integer()?;
        p.literal(b",\"query_digest\":\"sha256:", "query_digest")?;
        let query_digest = p.hex("query_digest")?;
        p.literal(b"\",\"policy_bundle\":\"sha256:", "policy_bundle")?;
        let policy_bundle = p.hex("policy_bundle")?;
        p.literal(b"\",\"image\":\"sha256:", "image")?;
        let image = p.hex("image")?;
        p.literal(b"\",\"cli_acceptance\":\"sha256:", "cli_acceptance")?;
        let cli_acceptance = p.hex("cli_acceptance")?;
        p.literal(b"\",\"configuration\":\"sha256:", "configuration")?;
        let configuration = p.hex("configuration")?;
        p.literal(b"\"}", "end")?;
        if p.at != bytes.len() {
            return Err(StartError::Syntax {
                field: "end",
                offset: p.at,
            });
        }
        let start = Self::new(
            StartFields {
                attempt,
                request,
                query_bytes,
                query_digest,
                policy_bundle,
                image,
                cli_acceptance,
                configuration,
            },
            limits,
        )?;
        let encoded = start.canonical_bytes();
        if encoded != bytes {
            return Err(StartError::NonCanonical {
                offset: encoded
                    .iter()
                    .zip(bytes)
                    .position(|(a, b)| a != b)
                    .unwrap_or(encoded.len().min(bytes.len())),
            });
        }
        Ok(start)
    }
}
fn append_hex(out: &mut String, value: &[u8; 32]) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for byte in value {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 15) as usize] as char);
    }
}
struct Parser<'a> {
    bytes: &'a [u8],
    at: usize,
}
impl Parser<'_> {
    fn literal(&mut self, expected: &[u8], field: &'static str) -> Result<(), StartError> {
        for byte in expected {
            if self.bytes.get(self.at) != Some(byte) {
                return Err(StartError::Syntax {
                    field,
                    offset: self.at,
                });
            }
            self.at += 1;
        }
        Ok(())
    }
    fn hex(&mut self, field: &'static str) -> Result<[u8; 32], StartError> {
        let mut out = [0; 32];
        for slot in &mut out {
            let mut byte = 0;
            for _ in 0..2 {
                let digit = match self.bytes.get(self.at) {
                    Some(b'0'..=b'9') => self.bytes[self.at] - b'0',
                    Some(b'a'..=b'f') => self.bytes[self.at] - b'a' + 10,
                    _ => {
                        return Err(StartError::Hex {
                            field,
                            offset: self.at,
                        });
                    }
                };
                byte = byte * 16 + digit;
                self.at += 1;
            }
            *slot = byte;
        }
        Ok(out)
    }
    fn integer(&mut self) -> Result<u32, StartError> {
        let begin = self.at;
        let mut value = 0u32;
        while let Some(b'0'..=b'9') = self.bytes.get(self.at) {
            value = value
                .checked_mul(10)
                .and_then(|v| v.checked_add((self.bytes[self.at] - b'0') as u32))
                .ok_or(StartError::Integer {
                    field: "query_bytes",
                    offset: self.at,
                })?;
            self.at += 1;
        }
        if begin == self.at || (self.bytes[begin] == b'0' && self.at > begin + 1) {
            return Err(StartError::Integer {
                field: "query_bytes",
                offset: begin,
            });
        }
        Ok(value)
    }
}
