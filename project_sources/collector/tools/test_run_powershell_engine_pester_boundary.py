#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from powershell_engine_pester_boundary_test_matrix import EngineBoundaryMatrixTestsMixin
from powershell_engine_pester_boundary_test_reports import EngineBoundaryReportTestsMixin
from powershell_engine_pester_boundary_test_support import (
    EngineBoundaryTestBase,
    boundary,
    good_boundary_doc,
    matrix_row,
    write,
    write_reports,
)


class PowerShellEnginePesterBoundaryTests(
    EngineBoundaryMatrixTestsMixin,
    EngineBoundaryReportTestsMixin,
    EngineBoundaryTestBase,
):
    pass


if __name__ == "__main__":
    raise SystemExit(unittest.main())
