#![forbid(unsafe_code)]

//! Axiom IR 内部组件。提供支持范围内的文档规范字节 / 身份、受限表达式与保守标签分析、契约类型 / 接口检查；尚未完成全语义 P1 验收。

pub mod contracts;
pub mod declarations;
pub mod document;
pub mod expressions;
pub mod integer;
pub mod json;
pub mod migration;
pub mod nodes;
pub mod normalization;
pub mod version;
