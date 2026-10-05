#![forbid(unsafe_code)]

//! Axiom IR、派生义务与限定查询内部组件。P1 检查文档，P2 生成身份，P3-A 编码目标；不提供证明、完整 Evidence 或执行门控。

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
pub mod query;
pub mod version;
