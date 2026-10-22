//! 只编码固定 profile 的闭合形状；计数与输出共用相同路径。

use super::{Obligation, ObligationKind};
use crate::json::emit_string;
use crate::version::V0_2_SEMANTICS_SHA256;

pub(super) enum Subject<'a> {
    Document,
    Program,
    Node(&'a str),
    Contract(&'a str),
    Path {
        contract: bool,
        id: &'a str,
        path: &'a [PathPart<'a>],
    },
    Field {
        interface: &'a str,
        name: &'a str,
    },
}

pub(super) enum PathPart<'a> {
    Name(&'a str),
    Index(usize),
}

pub(super) fn path(parts: &[PathPart<'_>], out: &mut impl FnMut(&[u8])) {
    out(b"[");
    for (index, part) in parts.iter().enumerate() {
        if index != 0 {
            out(b",");
        }
        match part {
            PathPart::Name(name) => emit_string(name, out),
            PathPart::Index(index) => emit_string(&index.to_string(), out),
        }
    }
    out(b"]");
}

pub(super) fn definition(
    kind: ObligationKind,
    subject: &Subject<'_>,
    document_id: &str,
    out: &mut impl FnMut(&[u8]),
) {
    out(b"{\"expectation\":");
    emit_string(kind.expectation(), out);
    out(b",\"kind\":");
    emit_string(kind.as_str(), out);
    out(b",\"subject\":{");
    let anchor = match subject {
        Subject::Field { interface, .. } => {
            out(b"\"direction\":\"output\",\"interface\":");
            emit_string(interface, out);
            out(b",");
            "field"
        }
        Subject::Node(id) | Subject::Contract(id) | Subject::Path { id, .. } => {
            out(b"\"id\":");
            emit_string(id, out);
            out(b",");
            match subject {
                Subject::Node(_) => "node",
                Subject::Contract(_) => "contract",
                Subject::Path { contract: true, .. } => "contract-path",
                _ => "node-path",
            }
        }
        Subject::Document => "document",
        Subject::Program => "program",
    };
    out(b"\"ir_document_digest\":");
    emit_string(document_id, out);
    out(b",\"kind\":");
    emit_string(anchor, out);
    match subject {
        Subject::Field { name, .. } => {
            out(b",\"name\":");
            emit_string(name, out);
        }
        Subject::Path { path: parts, .. } => {
            out(b",\"path\":");
            path(parts, out);
        }
        _ => {}
    }
    out(b"}}");
}

pub(super) fn entry(definition: &[u8], id: &str, out: &mut impl FnMut(&[u8])) {
    out(b"{\"definition\":");
    out(definition);
    out(b",\"id\":");
    emit_string(id, out);
    out(b"}");
}

pub(super) fn envelope(
    ir_artifact: &str,
    document_id: &str,
    entries: &[Obligation],
    out: &mut impl FnMut(&[u8]),
) {
    out(b"{\"format\":\"axiom-obligation-set\",\"format_version\":\"0.2\",\"ir_artifact\":");
    emit_string(ir_artifact, out);
    out(b",\"ir_document_digest\":");
    emit_string(document_id, out);
    out(b",\"ir_version\":\"0.2\",\"obligation_profile\":{\"name\":\"keyed-finite-table-verification\",\"version\":\"0.2\"},\"obligations\":[");
    for (index, item) in entries.iter().enumerate() {
        if index != 0 {
            out(b",");
        }
        entry(item.canonical_definition(), item.id(), out);
    }
    out(b"],\"scope\":\"ir-derived\",\"semantics\":{\"name\":\"keyed-finite-table-semantics\",\"sha256\":\"sha256:");
    out(V0_2_SEMANTICS_SHA256.as_bytes());
    out(b"\"}}");
}
