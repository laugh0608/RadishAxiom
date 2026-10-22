//! 明确属于 simulation 的材料声明；摘要一致不表示 acceptance 或宿主资格。
use crate::{HostError, HostLimits, Result, checked_size, compare, encoding::Writer, raw_digest};

#[derive(Clone, Copy)]
pub struct MaterialInput<'a> {
    pub bytes: &'a [u8],
    pub expected_raw_digest: &'a str,
    /// 该份材料自己的预算，另受 HostLimits 的单份与合计预算约束。
    pub byte_limit: usize,
}
#[derive(Clone, Copy)]
pub struct SimulationPayloadInput<'a> {
    pub platform: &'a str,
    pub cli_member: &'a str,
    pub archive: MaterialInput<'a>,
    pub cli: MaterialInput<'a>,
    pub inventory: MaterialInput<'a>,
    pub licenses: MaterialInput<'a>,
    pub acceptance: MaterialInput<'a>,
}
#[derive(Clone, Copy)]
pub struct SimulationHostInput<'a> {
    pub platform: &'a str,
    pub context: &'a str,
    pub host: MaterialInput<'a>,
    pub context_record: MaterialInput<'a>,
    pub daemon: MaterialInput<'a>,
    pub kernel: MaterialInput<'a>,
    pub runtime: MaterialInput<'a>,
    pub image: MaterialInput<'a>,
    pub bootstrap: MaterialInput<'a>,
    pub policy: MaterialInput<'a>,
}
#[derive(Clone, Copy)]
pub struct SimulationIdentityInput<'a> {
    pub payload: SimulationPayloadInput<'a>,
    pub host: SimulationHostInput<'a>,
}

pub struct SimulationIdentity {
    bytes: Vec<u8>,
    digest: String,
    archive_digest: String,
    cli_digest: String,
    acceptance_digest: String,
}
impl SimulationIdentity {
    pub fn new(input: SimulationIdentityInput<'_>, limits: HostLimits) -> Result<Self> {
        if input.payload.platform != "linux-arm64" || input.host.platform != "linux-arm64" {
            return Err(HostError::BindingMismatch("platform"));
        }
        if input.host.context != "orbstack" {
            return Err(HostError::BindingMismatch("context"));
        }
        if input.payload.cli_member != "cvc5-Linux-arm64-static/bin/cvc5" {
            return Err(HostError::BindingMismatch("cli_member"));
        }
        let p = input.payload;
        let h = input.host;
        let materials = [
            ("archive", p.archive),
            ("cli", p.cli),
            ("inventory", p.inventory),
            ("licenses", p.licenses),
            ("acceptance", p.acceptance),
            ("host", h.host),
            ("context", h.context_record),
            ("daemon", h.daemon),
            ("kernel", h.kernel),
            ("runtime", h.runtime),
            ("image", h.image),
            ("bootstrap", h.bootstrap),
            ("policy", h.policy),
        ];
        let mut total = 0;
        // 先核对所有预算，再读取、摘要或复制任何材料。
        for (_, material) in materials {
            if material.bytes.is_empty() {
                return Err(HostError::InvalidInput("empty simulation material"));
            }
            if material.bytes.len() > material.byte_limit
                || material.bytes.len() > limits.material_bytes
            {
                return Err(HostError::ResourceLimit("material_bytes"));
            }
            total = checked_size(
                total,
                material.bytes.len(),
                limits.total_material_bytes,
                "total_material_bytes",
            )?;
        }
        let mut out = Writer::new(limits.record_bytes);
        out.raw(b"{")?;
        out.field("format", "axiom-solver-simulation-identity")?;
        out.raw(b",")?;
        out.field("version", "0.1")?;
        out.raw(b",")?;
        out.field("scope", "simulation")?;
        out.raw(b",")?;
        out.field("platform", p.platform)?;
        out.raw(b",")?;
        out.field("context", h.context)?;
        out.raw(b",")?;
        out.field("cli_member", p.cli_member)?;
        out.raw(b",")?;
        out.field("claim_status", "simulation-only-not-accepted-not-qualified")?;
        out.raw(b",")?;
        out.key("materials")?;
        out.raw(b"{")?;
        for (index, (role, material)) in materials.into_iter().enumerate() {
            if index != 0 {
                out.raw(b",")?;
            }
            let actual = raw_digest(material.bytes);
            if actual != material.expected_raw_digest {
                return Err(HostError::BindingMismatch(role));
            }
            out.key(role)?;
            out.raw(b"{")?;
            out.field("scope", "simulation")?;
            out.raw(b",")?;
            out.field("raw_digest", &actual)?;
            out.raw(b",")?;
            out.field("byte_length", &material.bytes.len().to_string())?;
            out.raw(b",")?;
            out.key("raw_hex")?;
            out.hex(material.bytes)?;
            out.raw(b"}")?;
        }
        out.raw(b"}}")?;
        let bytes = out.finish(limits)?;
        let digest = raw_digest(&bytes);
        Ok(Self {
            bytes,
            digest,
            archive_digest: raw_digest(p.archive.bytes),
            cli_digest: raw_digest(p.cli.bytes),
            acceptance_digest: raw_digest(p.acceptance.bytes),
        })
    }
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn artifact_digest(&self) -> &str {
        &self.digest
    }
    pub fn archive_raw_digest(&self) -> &str {
        &self.archive_digest
    }
    pub fn cli_raw_digest(&self) -> &str {
        &self.cli_digest
    }
    pub fn acceptance_raw_digest(&self) -> &str {
        &self.acceptance_digest
    }
}

pub fn check_simulation_identity(
    bytes: &[u8],
    input: SimulationIdentityInput<'_>,
    limits: HostLimits,
) -> Result<SimulationIdentity> {
    if bytes.len() > limits.record_bytes {
        return Err(HostError::ResourceLimit("record_bytes"));
    }
    let identity = SimulationIdentity::new(input, limits)?;
    compare(
        bytes,
        identity.canonical_bytes(),
        "simulation-identity",
        limits,
    )?;
    Ok(identity)
}
