#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from powershell_report_ingestion_safety_test_engine import ReportIngestionEngineSafetyTestsMixin
from powershell_report_ingestion_safety_test_governance import ReportIngestionGovernanceSafetyTestsMixin
from powershell_report_ingestion_safety_test_support import (
    baseline_record,
    boundary,
    boundary_args,
    boundary_doc,
    boundary_matrix_row,
    finding,
    governance,
    governance_args,
    suppression_record,
    write,
    write_boundary_reports,
    write_governance_repo,
)


class PowerShellReportIngestionSafetyTests(
    ReportIngestionEngineSafetyTestsMixin,
    ReportIngestionGovernanceSafetyTestsMixin,
    unittest.TestCase,
):
    pass


if __name__ == "__main__":
    raise SystemExit(unittest.main())
