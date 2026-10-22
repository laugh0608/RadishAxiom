use super::{
    EffectProfile,
    rules::{PathPart, Step},
};
use crate::{
    document::CanonicalDocument, json::emit_string, obligations::ObligationSet,
    query::GeneratorIdentity,
};

pub(super) struct Binding<'a> {
    pub profile: EffectProfile,
    pub document: &'a CanonicalDocument,
    pub obligations: &'a ObligationSet,
    pub obligation_id: &'a str,
    pub generator: &'a GeneratorIdentity,
}
pub(super) fn path(parts: &[PathPart<'_>], out: &mut impl FnMut(&[u8])) {
    out(b"[");
    for (index, part) in parts.iter().enumerate() {
        if index > 0 {
            out(b",");
        }
        match part {
            PathPart::Name(name) => emit_string(name, out),
            PathPart::Index(index) => emit_string(&index.to_string(), out),
        }
    }
    out(b"]");
}
pub(super) fn envelope(binding: &Binding<'_>, steps: &[Step<'_>], out: &mut impl FnMut(&[u8])) {
    out(b"{\"binding\":{\"generator\":");
    emit_string(binding.generator.source_digest(), out);
    out(b",\"ir_artifact\":");
    emit_string(binding.obligations.ir_artifact(), out);
    out(b",\"ir_document_digest\":");
    emit_string(binding.document.document_id(), out);
    out(b",\"ir_version\":\"0.2\",\"obligation\":");
    emit_string(binding.obligation_id, out);
    out(b",\"obligation_set_artifact\":");
    emit_string(binding.obligations.artifact_digest(), out);
    out(b",\"semantics\":");
    emit_string(
        &format!("sha256:{}", binding.document.version().semantics_sha256()),
        out,
    );
    out(b"},\"format\":\"axiom-core-effect-derivation\",\"format_version\":\"0.1\",\"root\":");
    emit_string(&(steps.len() - 1).to_string(), out);
    out(b",\"rule_profile\":");
    emit_string(binding.profile.as_str(), out);
    out(b",\"steps\":[");
    for (index, step) in steps.iter().enumerate() {
        if index > 0 {
            out(b",");
        }
        out(b"{\"anchor\":{\"id\":");
        emit_string(step.anchor.id, out);
        out(b",\"kind\":");
        emit_string(step.anchor.kind, out);
        out(b"},\"path\":");
        path(&step.path, out);
        out(b",\"premises\":[");
        for (index, premise) in step.premises.iter().enumerate() {
            if index > 0 {
                out(b",");
            }
            emit_string(&premise.to_string(), out);
        }
        out(b"],\"rule\":");
        emit_string(&step.rule, out);
        out(b"}");
    }
    out(b"]}");
}
