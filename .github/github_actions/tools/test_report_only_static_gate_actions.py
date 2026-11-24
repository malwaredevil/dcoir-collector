#!/usr/bin/env python3
"""Issue #608 slice 1: report producers do not own static-analysis gating."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ANALYZER_ACTION = ".github/actions/run-psscriptanalyzer/action.yml"
DUPLICATE_ACTION = ".github/actions/run-duplicate-function-check/action.yml"
DUPLICATE_SCRIPT = ".github/actions/run-duplicate-function-check/Invoke-DcoirDuplicateFunctionCheck.ps1"
PR_WORKFLOW = ".github/workflows/reusable-validate-on-pr.yml"
PUSH_WORKFLOW = ".github/workflows/reusable-validate-on-push.yml"
CENTRAL_GATE = ".github/scripts/Test-DcoirStaticAnalysisValidationGate.ps1"
LEGACY_INPUTS = ("fail-" + "on-error-severity", "fail-" + "on-duplicates")


class ReportOnlyStaticGateContractTests(unittest.TestCase):
    def text(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_legacy_action_gates_have_no_callers_or_implementations(self) -> None:
        for path in (ANALYZER_ACTION, DUPLICATE_ACTION, DUPLICATE_SCRIPT, PR_WORKFLOW, PUSH_WORKFLOW):
            with self.subTest(path=path):
                data = self.text(path)
                for legacy_input in LEGACY_INPUTS:
                    self.assertNotIn(legacy_input, data)
                self.assertNotIn("FAIL_ON_ERROR_SEVERITY", data)
                self.assertNotIn("FAIL_ON_DUPLICATES", data)

    def test_report_producers_keep_fatal_integrity_checks(self) -> None:
        analyzer = self.text(ANALYZER_ACTION)
        self.assertIn("if ($LASTEXITCODE -ne 0)", analyzer)
        self.assertIn("if ($report.validation.success -ne $true)", analyzer)
        self.assertIn("--fail-on-severity Warning --allow-findings", analyzer)
        duplicate = self.text(DUPLICATE_SCRIPT)
        self.assertIn("if ($parseFailures.Count -gt 0)", duplicate)
        self.assertIn("throw \"Duplicate function check failed because", duplicate)
        self.assertIn("duplicate_function_count", duplicate)
        self.assertIn("Write-Warning 'Duplicate function definitions found;", duplicate)

    def test_central_gate_still_blocks_both_finding_classes(self) -> None:
        gate = self.text(CENTRAL_GATE)
        self.assertIn("if ($errorCount -gt 0)", gate)
        self.assertIn("if ($blockingCount -gt 0)", gate)
        self.assertIn("if ($duplicateCount -gt 0)", gate)
        self.assertIn("if ($parseFailureCount -gt 0)", gate)
        self.assertIn("STATIC ANALYSIS VALIDATION GATE FAILED", gate)
        self.assertIn("throw \"Static analysis validation gate failed", gate)

    def test_validation_workflows_retained_action_and_central_gate(self) -> None:
        for path in (PR_WORKFLOW, PUSH_WORKFLOW):
            with self.subTest(path=path):
                workflow = self.text(path)
                self.assertIn("uses: ./.github/actions/run-psscriptanalyzer", workflow)
                self.assertIn("uses: ./.github/actions/run-duplicate-function-check", workflow)
                self.assertIn("./.github/scripts/Test-DcoirStaticAnalysisValidationGate.ps1", workflow)


if __name__ == "__main__":
    unittest.main()
