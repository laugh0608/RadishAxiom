#![forbid(unsafe_code)]

//! Axiom IR 与 IR 派生义务内部组件。P1 检查 / 规范化文档，P2 生成位置与身份；不提供证明、完整 Evidence 或执行门控。

pub mod contracts;
pub mod declarations;
pub mod document;
pub mod expressions;
pub mod integer;
pub mod json;
pub mod migration;
pub mod nodes;
pub mod normalization;
pub mod obligations;
pub mod version;
