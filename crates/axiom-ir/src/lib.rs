#![forbid(unsafe_code)]

//! Axiom IR 内部组件。当前提供 JSON 字节边界与类型声明解码，不提供完整 IR 验收入口。

pub mod declarations;
pub mod integer;
pub mod json;
