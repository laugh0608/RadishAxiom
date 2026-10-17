//! v0.5 独立逻辑资源账本；旧六项结构和调用保持原状。
use super::{QueryError, QueryLimits, Result};

#[derive(Clone, Copy, Debug)]
pub struct QueryBudgets {
    pub base: QueryLimits,
    pub compact: Option<CompactQueryLimits>,
}
impl From<QueryLimits> for QueryBudgets {
    fn from(base: QueryLimits) -> Self {
        Self {
            base,
            compact: None,
        }
    }
}
impl QueryLimits {
    pub fn with_compact(self, compact: CompactQueryLimits) -> QueryBudgets {
        QueryBudgets {
            base: self,
            compact: Some(compact),
        }
    }
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CompactQueryLimits {
    pub max_normalized_nodes: usize,
    pub max_normalized_edges: usize,
    pub max_scratch_cells: usize,
    pub max_work_steps: usize,
    pub max_temporary_bytes: usize,
    pub max_integer_digits: usize,
    pub max_dag_depth: usize,
}
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct CompactQueryUsage {
    pub normalized_nodes: usize,
    pub normalized_edges: usize,
    pub scratch_cells: usize,
    pub work_steps: usize,
    pub temporary_bytes: usize,
    pub integer_digits: usize,
    pub dag_depth: usize,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CompactQueryResource {
    NormalizedNodes,
    NormalizedEdges,
    ScratchCells,
    WorkSteps,
    TemporaryBytes,
    IntegerDigits,
    DagDepth,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum QueryStage {
    Construction,
    Normalization,
    Rendering,
}

pub(super) struct Meter {
    pub limits: CompactQueryLimits,
    pub usage: CompactQueryUsage,
    pub obligation: String,
    pub stage: QueryStage,
}
impl Meter {
    pub fn new(limits: CompactQueryLimits, obligation: String) -> Self {
        Self {
            limits,
            usage: CompactQueryUsage::default(),
            obligation,
            stage: QueryStage::Normalization,
        }
    }
    pub fn error(&self, resource: CompactQueryResource) -> QueryError {
        QueryError::CompactResourceLimit {
            resource,
            obligation: self.obligation.clone(),
            stage: self.stage,
        }
    }
    pub fn add(&self, a: usize, b: usize, resource: CompactQueryResource) -> Result<usize> {
        a.checked_add(b).ok_or_else(|| self.error(resource))
    }
    pub fn mul(&self, a: usize, b: usize, resource: CompactQueryResource) -> Result<usize> {
        a.checked_mul(b).ok_or_else(|| self.error(resource))
    }
    pub fn charge(&mut self, resource: CompactQueryResource, amount: usize) -> Result<()> {
        use CompactQueryResource::*;
        let (used, limit, maximum) = match resource {
            NormalizedNodes => (
                &mut self.usage.normalized_nodes,
                self.limits.max_normalized_nodes,
                false,
            ),
            NormalizedEdges => (
                &mut self.usage.normalized_edges,
                self.limits.max_normalized_edges,
                false,
            ),
            ScratchCells => (
                &mut self.usage.scratch_cells,
                self.limits.max_scratch_cells,
                false,
            ),
            WorkSteps => (
                &mut self.usage.work_steps,
                self.limits.max_work_steps,
                false,
            ),
            TemporaryBytes => (
                &mut self.usage.temporary_bytes,
                self.limits.max_temporary_bytes,
                false,
            ),
            IntegerDigits => (
                &mut self.usage.integer_digits,
                self.limits.max_integer_digits,
                true,
            ),
            DagDepth => (&mut self.usage.dag_depth, self.limits.max_dag_depth, true),
        };
        let next = if maximum {
            Some((*used).max(amount))
        } else {
            used.checked_add(amount)
        };
        if let Some(value) = next.filter(|v| *v <= limit) {
            *used = value;
            Ok(())
        } else {
            Err(self.error(resource))
        }
    }
    pub fn work(&mut self, amount: usize) -> Result<()> {
        self.charge(CompactQueryResource::WorkSteps, amount)
    }
    pub fn cells(&mut self, amount: usize) -> Result<()> {
        self.charge(CompactQueryResource::ScratchCells, amount)?;
        // Prepay one initialization / copy visit for each newly reserved logical cell.
        self.work(amount)
    }
    pub fn bytes(&mut self, amount: usize) -> Result<()> {
        self.charge(CompactQueryResource::TemporaryBytes, amount)?;
        self.work(amount)
    }
    pub fn copy(&mut self, value: &str) -> Result<String> {
        self.bytes(value.len())?;
        Ok(value.to_owned())
    }
}
