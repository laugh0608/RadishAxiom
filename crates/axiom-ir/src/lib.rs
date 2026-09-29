#![forbid(unsafe_code)]

//! Axiom IR 内部组件。提供 JSON 字节边界、类型声明解码与身份核对，不提供完整 IR 验收入口。

pub mod declarations;
pub mod integer;
pub mod json;
pub mod normalization;
