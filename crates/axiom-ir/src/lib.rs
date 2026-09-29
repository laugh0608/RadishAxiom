#![forbid(unsafe_code)]

//! Axiom IR 内部组件。提供 JSON、类型声明身份及逐行表达式类型检查，不提供完整 IR 验收入口。

pub mod declarations;
pub mod expressions;
pub mod integer;
pub mod json;
pub mod normalization;
