#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum PortablePathError {
    Absolute,
    Component,
    Character,
}

pub(crate) fn validate_portable_relative_path(value: &str) -> Result<(), PortablePathError> {
    if value.is_empty() || value.starts_with('/') || value.starts_with('\\') {
        return Err(PortablePathError::Absolute);
    }
    for component in value.split('/') {
        if component.is_empty() || matches!(component, "." | "..") {
            return Err(PortablePathError::Component);
        }
        if !component
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
        {
            return Err(PortablePathError::Character);
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{PortablePathError, validate_portable_relative_path};

    #[test]
    fn portable_relative_paths_are_closed() {
        assert!(validate_portable_relative_path("payload/checker-v0.1").is_ok());
        for (value, error) in [
            ("", PortablePathError::Absolute),
            ("/absolute", PortablePathError::Absolute),
            ("\\absolute", PortablePathError::Absolute),
            ("payload//checker", PortablePathError::Component),
            ("payload/../checker", PortablePathError::Component),
            ("payload/checker\\alias", PortablePathError::Character),
        ] {
            assert_eq!(validate_portable_relative_path(value), Err(error));
        }
    }
}
