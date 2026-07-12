#!/usr/bin/env python3
"""Compatibility facade for PowerShell custom-check runner tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from powershell_custom_checks_test_analyzer import AnalyzerSkipCustomCheckMixin
from powershell_custom_checks_test_common import PowerShellCustomCheckCase
from powershell_custom_checks_test_fail_output import FailOutputCustomCheckMixin
from powershell_custom_checks_test_paths import PathSafetyAndContractCustomCheckMixin


class PowerShellCustomCheckTests(
    FailOutputCustomCheckMixin,
    AnalyzerSkipCustomCheckMixin,
    PathSafetyAndContractCustomCheckMixin,
    PowerShellCustomCheckCase,
):
    pass


if __name__ == "__main__":
    raise SystemExit(unittest.main())
