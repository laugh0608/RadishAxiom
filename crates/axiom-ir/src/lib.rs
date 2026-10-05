#![forbid(unsafe_code)]

//! Axiom IR 内部组件。提供 JSON、声明身份、逐行表达式类型及节点图分析，不提供完整 IR 验收入口。

pub mod declarations;
pub mod expressions;
pub mod integer;
pub mod json;
pub mod nodes;
pub mod normalization;
