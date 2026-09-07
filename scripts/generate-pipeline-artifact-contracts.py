#!/usr/bin/env python3
"""Generate Pipeline Artifact Contract v0.1 schemas and fixtures.

This dependency-free generator validates contract fixtures. It is not a Rust
compiler, SMT parser, ECMAScript parser, solver adapter, Node launcher, Evidence
producer, or independent checker.
"""

from pipeline_artifact_contracts.generator import main


if __name__ == "__main__":
    raise SystemExit(main())
