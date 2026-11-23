#!/usr/bin/env python3
"""Issue #608 Slice 3: documentation action consumes a caller-assembled harness."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACTION = ROOT / ".github/actions/run-collector-documentation-quality/action.yml"
CALLERS = (
    ".github/workflows/reusable-validate-on-pr.yml",
    ".github/workflows/reusable-validate-on-push.yml",
    ".github/workflows/reusable-collector-documentation-quality.yml",
    ".github/workflows/reusable-collector-validation.yml",
    ".github/workflows/reusable-collector-runtime-package-build.yml",
)
ASSEMBLER_CALL = "uses: ./.github/actions/assemble-collector-harness"
DOC_CALL = "uses: ./.github/actions/run-collector-documentation-quality"


class CollectorHarnessReuseTests(unittest.TestCase):
    def test_documentation_action_requires_preassembled_harness(self) -> None:
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn("Preassembled collector harness missing:", text)
        self.assertIn("run_DCOIR_Tests.generated.ps1", text)
        self.assertIn("Test-Path -LiteralPath $generatedHarnessPath -PathType Leaf", text)
        self.assertNotIn("& $assemblerPath -OutputPath", text)

    def test_every_documentation_workflow_assembles_before_consuming(self) -> None:
        for name in CALLERS:
            with self.subTest(workflow=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn(DOC_CALL, text)
                self.assertIn(ASSEMBLER_CALL, text)
                self.assertLess(text.index(ASSEMBLER_CALL), text.index(DOC_CALL))

    def test_conditional_validation_workflow_assembles_for_docs_only(self) -> None:
        text = (ROOT / ".github/workflows/reusable-collector-validation.yml").read_text(encoding="utf-8")
        self.assertIn(
            "inputs.run_harness_assembly_parity || inputs.run_harness_suite || inputs.run_documentation_quality",
            text,
        )

    def test_documentation_action_still_runs_actual_validator(self) -> None:
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn("python project_sources/collector/tools/test_verify_collector_documentation_quality.py", text)
        self.assertIn("'project_sources/collector/tools/verify_collector_documentation_quality.py'", text)
        self.assertIn("throw 'Collector documentation quality gate failed.'", text)


if __name__ == "__main__":
    unittest.main()
