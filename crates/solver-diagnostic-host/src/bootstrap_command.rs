//! Independent offline command input. Reads the same fixed argument tokens as
//! SolverRequest; it neither accepts runtime argv nor changes F1's four files.
use crate::{HostError, Result, raw_digest};
use radishaxiom_ir::solver::ARGUMENT_TOKENS;
use std::fmt::Write;

pub const COMMAND_MAGIC: &[u8; 8] = b"AXBCMD01";
pub const COMMAND_FORMAT: &str = "solver-bootstrap-command-input-v0.1";
pub const COMMAND_GENERATOR: &str =
    "crates/solver-diagnostic-host/examples/solver_bootstrap_command.rs";
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OfflineCommandInput {
    pub command: Vec<u8>,
    pub manifest: Vec<u8>,
}
fn command_bytes() -> Vec<u8> {
    let mut bytes = Vec::from(COMMAND_MAGIC.as_slice());
    bytes.extend_from_slice(&(ARGUMENT_TOKENS.len() as u32).to_be_bytes());
    for token in ARGUMENT_TOKENS {
        bytes.extend_from_slice(&(token.len() as u32).to_be_bytes());
        bytes.extend_from_slice(token.as_bytes());
    }
    bytes
}
pub fn export_offline_command() -> OfflineCommandInput {
    macro_rules! source {
        ($path:literal) => {
            (
                $path,
                include_bytes!(concat!("../../../", $path)).as_slice(),
            )
        };
    }
    let sources = [
        source!("Cargo.toml"),
        source!("Cargo.lock"),
        source!("rust-toolchain.toml"),
        source!("crates/axiom-ir/src/solver.rs"),
        source!("crates/digest/Cargo.toml"),
        source!("crates/digest/src/lib.rs"),
        source!("crates/solver-diagnostic-host/Cargo.toml"),
        source!("crates/solver-diagnostic-host/src/lib.rs"),
        source!("crates/solver-diagnostic-host/src/bootstrap_command.rs"),
        source!("crates/solver-diagnostic-host/examples/solver_bootstrap_command.rs"),
    ];
    let mut inventory = String::from("[");
    for (index, (path, bytes)) in sources.into_iter().enumerate() {
        if index != 0 {
            inventory.push(',');
        }
        write!(
            inventory,
            "{{\"path\":\"{path}\",\"bytes\":{},\"digest\":\"{}\"}}",
            bytes.len(),
            raw_digest(bytes)
        )
        .expect("String write");
    }
    inventory.push(']');
    let command = command_bytes();
    let manifest=format!(concat!("{{\"format\":\"{}\",\"scope\":\"offline-command-inputs-only\",",
        "\"generator\":\"{}\",\"source_inventory_digest\":\"{}\",\"sources\":{},",
        "\"command\":{{\"file\":\"command.bin\",\"bytes\":{},\"digest\":\"{}\"}},\"native_build\":\"not-accepted\"}}"),
        COMMAND_FORMAT,COMMAND_GENERATOR,raw_digest(inventory.as_bytes()),inventory,command.len(),raw_digest(&command)).into_bytes();
    OfflineCommandInput { command, manifest }
}
pub fn check_offline_command(input: &OfflineCommandInput) -> Result<()> {
    let expected = export_offline_command();
    if input.command != expected.command {
        return Err(HostError::BindingMismatch("command input"));
    }
    if input.manifest != expected.manifest {
        return Err(HostError::BindingMismatch("command manifest"));
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn same_twelve_tokens_and_corruption_rejected() {
        let input = export_offline_command();
        check_offline_command(&input).unwrap();
        assert_eq!(&input.command[..8], COMMAND_MAGIC);
        assert_eq!(&input.command[8..12], &12u32.to_be_bytes());
        let mut offset = 12;
        assert!(input.command.len() <= 4096);
        for token in ARGUMENT_TOKENS {
            assert!(
                (1..=128).contains(&token.len())
                    && token.starts_with("--")
                    && token.bytes().all(|b| (0x21..=0x7e).contains(&b))
            );
            let length =
                u32::from_be_bytes(input.command[offset..offset + 4].try_into().unwrap()) as usize;
            offset += 4;
            assert_eq!(&input.command[offset..offset + length], token.as_bytes());
            offset += length;
        }
        assert_eq!(offset, input.command.len());
        let mut bad = input.clone();
        bad.command[16] ^= 1;
        assert!(check_offline_command(&bad).is_err());
        let mut bad = input;
        bad.manifest.push(b' ');
        assert!(check_offline_command(&bad).is_err());
    }
}
