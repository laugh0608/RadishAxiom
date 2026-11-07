#![forbid(unsafe_code)]

//! Axiom IR、派生义务、限定查询和具体输入检查内部组件。

pub mod contracts;
pub mod declarations;
pub mod document;
pub mod effects;
pub mod evidence_review;
pub mod expressions;
pub mod fixtures;
pub mod host_data;
pub mod integer;
pub mod json;
pub mod migration;
pub mod nodes;
pub mod normalization;
pub mod obligations;
pub mod origins;
pub mod query;
pub mod replay;
pub mod solver;
pub mod version;
