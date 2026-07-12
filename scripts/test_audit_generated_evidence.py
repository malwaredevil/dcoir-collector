#!/usr/bin/env python3
"""Tests for generated evidence classification policy."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import sys
import unittest

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_generated_evidence as audit


class GeneratedEvidenceAuditTests(unittest.TestCase):
    def test_canonical_collector_report_is_classified(self) -> None:
        path = PurePosixPath("project_sources/collector/powershell_surface_inventory.json")
        self.assertIn("canonical_collector_reports", audit.classify(path))

    def test_nested_tool_with_report_in_name_is_not_canonical_report(self) -> None:
        path = PurePosixPath("project_sources/collector/tools/report_helper.py")
        self.assertNotIn("canonical_collector_reports", audit.classify(path))

    def test_report_chunks_are_policy_violations(self) -> None:
        path = PurePosixPath("project_sources/collector/report_chunks/task/chunk_001.txt")
        self.assertIn("durable_report_chunks", audit.classify(path))

    def test_status_report_is_both_staging_and_status(self) -> None:
        path = PurePosixPath("chatgpt_staging/status_reports/workflow/id/workflow_report.md")
        classes = audit.classify(path)
        self.assertIn("chatgpt_staging", classes)
        self.assertIn("chatgpt_status_reports", classes)

    def test_fixture_classification_is_independent(self) -> None:
        path = PurePosixPath("project_sources/collector/fixtures/example/report.json")
        classes = audit.classify(path)
        self.assertIn("fixtures", classes)
        self.assertNotIn("canonical_collector_reports", classes)


if __name__ == "__main__":
    unittest.main()
