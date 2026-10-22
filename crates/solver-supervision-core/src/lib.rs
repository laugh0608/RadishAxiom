#![forbid(unsafe_code)]

//! Private pure supervision rules. Parsing establishes no source authenticity,
//! operating-system capability, runtime qualification, or execution permission.
pub mod abi;
pub mod bootstrap_start;
pub mod cgroup;
pub mod handshake;
pub mod policy;
pub mod wire;

pub fn raw_digest(bytes: &[u8]) -> String {
    format!("sha256:{}", radishaxiom_digest::digest_hex(bytes))
}
