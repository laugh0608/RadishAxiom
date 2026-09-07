use std::error::Error;
use std::fmt;

use crate::canonical::{DocumentError, Value, as_object, string_member};
use crate::policy::LauncherPolicy;
use crate::registration::{RegistrationRecord, RegistrationStatus};

#[derive(Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct NativeTarget {
    goos: Box<str>,
    goarch: Box<str>,
    variant: Box<str>,
    executable_format: Box<str>,
}

impl NativeTarget {
    pub fn try_new(
        goos: impl Into<Box<str>>,
        goarch: impl Into<Box<str>>,
        variant: impl Into<Box<str>>,
        executable_format: impl Into<Box<str>>,
    ) -> Result<Self, DocumentError> {
        let target = Self {
            goos: goos.into(),
            goarch: goarch.into(),
            variant: variant.into(),
            executable_format: executable_format.into(),
        };
        for (name, value) in [
            ("goos", target.goos.as_ref()),
            ("goarch", target.goarch.as_ref()),
            ("goarm64", target.variant.as_ref()),
            ("executable_format", target.executable_format.as_ref()),
        ] {
            if !valid_component(value) {
                return Err(DocumentError::new(
                    "invalid-target-component",
                    format!("$.target.{name}"),
                ));
            }
        }
        Ok(target)
    }

    pub fn goos(&self) -> &str {
        &self.goos
    }

    pub fn goarch(&self) -> &str {
        &self.goarch
    }

    pub fn variant(&self) -> &str {
        &self.variant
    }

    pub fn executable_format(&self) -> &str {
        &self.executable_format
    }

    pub(crate) fn from_value(value: &Value, path: &str) -> Result<Self, DocumentError> {
        let object = as_object(value, path)?;
        Self::try_new(
            string_member(object, "goos", path)?,
            string_member(object, "goarch", path)?,
            string_member(object, "goarm64", path)?,
            string_member(object, "executable_format", path)?,
        )
        .map_err(|error| DocumentError::new(error.code(), path))
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NativeProcessMode {
    Native,
    Translated,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NativeHostIdentity {
    target: NativeTarget,
    process_mode: NativeProcessMode,
}

impl NativeHostIdentity {
    pub fn new(target: NativeTarget, process_mode: NativeProcessMode) -> Self {
        Self {
            target,
            process_mode,
        }
    }

    pub fn target(&self) -> &NativeTarget {
        &self.target
    }

    pub fn process_mode(&self) -> NativeProcessMode {
        self.process_mode
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SelectionPurpose {
    Product,
    Qualification,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SelectionError {
    TranslatedProcess,
    UnsupportedTarget,
    Cardinality {
        required_status: RegistrationStatus,
        actual: usize,
    },
}

impl SelectionError {
    pub fn classification(&self) -> &'static str {
        "runtime-unavailable"
    }
}

impl fmt::Display for SelectionError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TranslatedProcess => write!(formatter, "translated-process"),
            Self::UnsupportedTarget => write!(formatter, "unsupported-target"),
            Self::Cardinality {
                required_status,
                actual,
            } => write!(
                formatter,
                "selection-cardinality: expected one {required_status}, found {actual}"
            ),
        }
    }
}

impl Error for SelectionError {}

pub fn select_registration<'a>(
    policy: &LauncherPolicy,
    records: &'a [RegistrationRecord],
    host: &NativeHostIdentity,
    purpose: SelectionPurpose,
) -> Result<&'a RegistrationRecord, SelectionError> {
    if host.process_mode == NativeProcessMode::Translated {
        return Err(SelectionError::TranslatedProcess);
    }
    if !policy.supports(&host.target) {
        return Err(SelectionError::UnsupportedTarget);
    }

    let required_status = match purpose {
        SelectionPurpose::Product => RegistrationStatus::Active,
        SelectionPurpose::Qualification => RegistrationStatus::RegisteredInactive,
    };
    let mut matches = records
        .iter()
        .filter(|record| record.target() == &host.target && record.status() == required_status);
    let selected = matches.next();
    let second = matches.next();
    match (selected, second) {
        (Some(record), None) => Ok(record),
        (None, _) => Err(SelectionError::Cardinality {
            required_status,
            actual: 0,
        }),
        (Some(_), Some(_)) => Err(SelectionError::Cardinality {
            required_status,
            actual: records
                .iter()
                .filter(|record| {
                    record.target() == &host.target && record.status() == required_status
                })
                .count(),
        }),
    }
}

fn valid_component(value: &str) -> bool {
    let mut bytes = value.bytes();
    matches!(bytes.next(), Some(first) if first.is_ascii_lowercase() || first.is_ascii_digit())
        && bytes.all(|byte| {
            byte.is_ascii_lowercase() || byte.is_ascii_digit() || matches!(byte, b'.' | b'-')
        })
        && !matches!(value, "." | "..")
}

#[cfg(test)]
mod tests {
    use super::NativeTarget;

    #[test]
    fn target_components_are_closed_and_path_safe() {
        assert!(NativeTarget::try_new("darwin", "arm64", "v8.0", "macho-64-arm64").is_ok());
        for invalid in ["", ".", "..", "Arm64", "../arm64", "arm64_unsafe"] {
            assert!(NativeTarget::try_new("darwin", invalid, "v8.0", "macho-64-arm64").is_err());
        }
    }
}
