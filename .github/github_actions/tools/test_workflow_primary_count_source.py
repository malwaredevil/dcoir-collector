#!/usr/bin/env python3
"""Regression tests for a single, fail-closed primary workflow count owner."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import audit_reusable_contract_checks as checks


class PrimaryWorkflowCountSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.primary = self.root / "validate.yml"
        self.primary.write_text("name: Validate\non: push\n", encoding="utf-8")

    def audit(self, declared: object, files: list[Path] | None = None) -> list[str]:
        findings: list[str] = []
        with patch.object(checks, "read_contracts", return_value={"existing_workflow_count": declared}):
            checks.check_reusable_workflows(
                self.root,
                [self.primary] if files is None else files,
                findings,
            )
        return findings

    def test_matching_registry_count_passes(self) -> None:
        self.assertEqual(self.audit(1), [])

    def test_registry_count_above_reality_fails(self) -> None:
        self.assertTrue(any("expected 2 primary workflows, found 1" in s for s in self.audit(2)))

    def test_registry_count_below_reality_fails(self) -> None:
        self.assertTrue(any("expected 0 primary workflows, found 1" in s for s in self.audit(0)))

    def test_invalid_registry_count_fails_closed(self) -> None:
        for invalid in (None, True, False, "1", 1.0, -1, []):
            with self.subTest(invalid=invalid):
                self.assertTrue(
                    any("existing_workflow_count must be a non-negative integer" in s
                        for s in self.audit(invalid))
                )

    def test_empty_workflow_tree_with_explicit_zero_passes(self) -> None:
        self.assertEqual(self.audit(0, files=[]), [])

    def test_reusable_workflow_is_not_in_primary_count(self) -> None:
        reusable = self.root / "reusable-build.yml"
        reusable.write_text(
            "name: Reusable Build\non:\n  workflow_call:\npermissions:\n  contents: read\n",
            encoding="utf-8",
        )
        self.assertEqual(self.audit(1, files=[self.primary, reusable]), [])

    def test_broken_registry_loader_does_not_silently_pass(self) -> None:
        with patch.object(checks, "read_contracts", side_effect=ValueError("invalid JSON")):
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                checks.check_reusable_workflows(self.root, [self.primary], [])


if __name__ == "__main__":
    unittest.main()
