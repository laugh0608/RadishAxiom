#!/usr/bin/env python3
"""Run dependency-free synthetic checks for the checker runtime launcher core."""

from __future__ import annotations

import sys

from checker_runtime_launcher.tests import run


if __name__ == "__main__":
    raise SystemExit(run())
