//! 精确版本、语义快照与内容身份域；不按范围或 latest 推断兼容性。

pub const V0_1_SEMANTICS_SHA256: &str =
    "6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d";
pub const V0_2_SEMANTICS_SHA256: &str =
    "a40ec7c4eecfde23a340fb61b67727b5393f01b7288d151a34168ec88a87dac7";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum IrVersion {
    V0_1,
    V0_2,
}

impl IrVersion {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::V0_1 => "0.1",
            Self::V0_2 => "0.2",
        }
    }

    pub fn semantics_sha256(self) -> &'static str {
        match self {
            Self::V0_1 => V0_1_SEMANTICS_SHA256,
            Self::V0_2 => V0_2_SEMANTICS_SHA256,
        }
    }

    pub(crate) fn parse(value: &str) -> Option<Self> {
        match value {
            "0.1" => Some(Self::V0_1),
            "0.2" => Some(Self::V0_2),
            _ => None,
        }
    }

    pub(crate) fn domain(self, kind: ContentKind) -> String {
        format!("axiom-ir-v{}:{}", self.as_str(), kind.as_str())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub enum ContentKind {
    EnumType,
    RecordType,
    TableType,
    Node,
    Contract,
    Document,
}

impl ContentKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::EnumType => "enum-type",
            Self::RecordType => "record-type",
            Self::TableType => "table-type",
            Self::Node => "node",
            Self::Contract => "contract",
            Self::Document => "document",
        }
    }
}

#[cfg(test)]
mod tests;
