use super::{
    OriginProfile,
    build::{Labels, Part, Pruned, Step, Target},
};
use crate::{
    declarations::Label, document::CanonicalDocument, json::emit_string,
    obligations::ObligationSet, query::GeneratorIdentity,
};
pub(super) struct Binding<'a> {
    pub profile: OriginProfile,
    pub document: &'a CanonicalDocument,
    pub obligations: &'a ObligationSet,
    pub obligation_id: &'a str,
    pub generator: &'a GeneratorIdentity,
}
pub(super) fn path(parts: &[Part<'_>], out: &mut impl FnMut(&[u8])) {
    out(b"[");
    for (i, p) in parts.iter().enumerate() {
        if i > 0 {
            out(b",");
        }
        match p {
            Part::Name(s) => emit_string(s, out),
            Part::Index(n) => emit_string(&n.to_string(), out),
        }
    }
    out(b"]");
}
fn label(v: Label, out: &mut impl FnMut(&[u8])) {
    emit_string(
        match v {
            Label::Public => "public",
            Label::Sensitive => "sensitive",
        },
        out,
    );
}
fn labels(v: Labels, out: &mut impl FnMut(&[u8])) {
    out(b"{\"declared\":");
    label(v.declared, out);
    out(b",\"inferred\":");
    label(v.inferred, out);
    out(b",\"propagated\":");
    label(v.propagated, out);
    out(b",\"type_summary\":");
    label(v.type_summary, out);
    out(b"}");
}
pub(super) fn envelope(
    binding: &Binding<'_>,
    steps: &[Step<'_>],
    target: &Target<'_>,
    pruned: &Pruned,
    out: &mut impl FnMut(&[u8]),
) {
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
    out(b"},\"format\":\"axiom-core-field-origin-derivation\",\"format_version\":\"0.1\",\"gaps\":[");
    let mut first = true;
    for (i, &id) in pruned.order.iter().enumerate() {
        if steps[id].gap {
            if !first {
                out(b",");
            }
            first = false;
            emit_string(&i.to_string(), out);
        }
    }
    out(b"],\"roots\":{\"control\":");
    emit_string(&pruned.remap[target.control].to_string(), out);
    out(b",\"evaluation\":");
    emit_string(&pruned.remap[target.evaluation].to_string(), out);
    out(b",\"value\":");
    emit_string(&pruned.remap[target.value].to_string(), out);
    out(b"},\"rule_profile\":");
    emit_string(binding.profile.as_str(), out);
    out(b",\"steps\":[");
    for (i, &id) in pruned.order.iter().enumerate() {
        if i > 0 {
            out(b",");
        }
        let step = &steps[id];
        out(b"{\"anchor\":{\"id\":");
        emit_string(step.anchor.id, out);
        out(b",\"kind\":");
        emit_string(step.anchor.kind, out);
        out(b"},\"gap\":");
        out(if step.gap { b"true" } else { b"false" });
        out(b",\"item\":");
        emit_string(step.item, out);
        out(b",\"labels\":");
        labels(step.labels, out);
        out(b",\"path\":");
        path(&step.path, out);
        out(b",\"premises\":[");
        for (j, edge) in step.premises.iter().enumerate() {
            if j > 0 {
                out(b",");
            }
            out(b"{\"role\":");
            emit_string(edge.role.name(), out);
            out(b",\"step\":");
            emit_string(&pruned.remap[edge.step].to_string(), out);
            out(b"}");
        }
        out(b"],\"rule\":");
        emit_string(&step.rule, out);
        out(b"}");
    }
    out(b"],\"target\":{\"interface\":");
    emit_string(target.interface, out);
    out(b",\"name\":");
    emit_string(target.name, out);
    out(b",\"node\":");
    emit_string(target.node, out);
    out(b",\"record_type\":");
    emit_string(target.record_type, out);
    out(b"}}");
}
