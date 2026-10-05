#![forbid(unsafe_code)]

//! Axiom IR 内部组件。提供 JSON、声明身份、受限表达式规范化、节点图 / 身份及保守标签分析，不提供完整 IR 验收入口。

pub mod declarations;
pub mod expressions;
pub mod integer;
pub mod json;
pub mod nodes;
pub mod normalization;
