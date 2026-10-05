#![forbid(unsafe_code)]

//! Axiom IR 内部组件。提供 JSON、声明身份、受限表达式规范化及节点图 / 身份检查，不提供完整 IR 验收入口。

pub mod declarations;
pub mod expressions;
pub mod integer;
pub mod json;
pub mod nodes;
pub mod normalization;
