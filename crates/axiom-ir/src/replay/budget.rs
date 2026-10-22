use super::{ReplayError, ReplayLimits, ReplayResource as R, ReplayStage, ReplayUsage, Result};

pub(super) struct Budget {
    pub limits: ReplayLimits,
    pub usage: ReplayUsage,
    pub stage: ReplayStage,
}
impl Budget {
    pub fn new(limits: ReplayLimits) -> Self {
        Self {
            limits,
            usage: ReplayUsage::default(),
            stage: ReplayStage::Binding,
        }
    }
    pub fn error(&self, resource: R) -> ReplayError {
        ReplayError::ResourceLimit {
            stage: self.stage,
            resource,
        }
    }
    fn slot(&mut self, r: R) -> (&mut usize, usize) {
        macro_rules! slot {
            ($field:ident) => {
                (&mut self.usage.$field, self.limits.$field)
            };
        }
        match r {
            R::WorldBytes => slot!(world_bytes),
            R::WorldNodes => slot!(world_nodes),
            R::WorldDepth => slot!(world_depth),
            R::TypeItems => slot!(type_items),
            R::Rows => slot!(rows),
            R::ValueCells => slot!(value_cells),
            R::EvaluationSteps => slot!(evaluation_steps),
            R::Comparisons => slot!(comparisons),
            R::IntegerDigits => slot!(integer_digits),
            R::DigitWork => slot!(digit_work),
            R::TextBytes => slot!(text_bytes),
            R::PathBytes => slot!(path_bytes),
            R::OutputBytes => slot!(output_bytes),
        }
    }
    pub fn charge(&mut self, r: R, n: usize) -> Result<()> {
        let (used, max) = self.slot(r);
        let Some(next) = used.checked_add(n).filter(|v| *v <= max) else {
            return Err(self.error(r));
        };
        *used = next;
        Ok(())
    }
    pub fn observe(&mut self, r: R, n: usize) -> Result<()> {
        let (used, max) = self.slot(r);
        if n > max {
            return Err(self.error(r));
        }
        *used = (*used).max(n);
        Ok(())
    }
    pub fn step(&mut self) -> Result<()> {
        self.charge(R::EvaluationSteps, 1)
    }
    pub fn copy(&mut self, s: &str) -> Result<String> {
        self.charge(R::ValueCells, s.len())?;
        Ok(s.to_owned())
    }
    pub fn text_copy(&mut self, s: &str) -> Result<String> {
        self.charge(R::TextBytes, s.len())?;
        self.copy(s)
    }
}
