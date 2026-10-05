#![forbid(unsafe_code)]

//! Axiom IR 内部组件。提供声明 / 节点身份、受限表达式与保守标签分析、契约类型 / 接口检查，不提供完整 IR 验收入口。

pub mod contracts;
pub mod declarations;
pub mod expressions;
pub mod integer;
pub mod json;
pub mod nodes;
pub mod normalization;
