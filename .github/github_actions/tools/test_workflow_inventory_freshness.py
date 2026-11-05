#!/usr/bin/env python3
"""Hostile parity tests for the one canonical workflow-inventory freshness check."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lib.workflow_inventory_outputs import check_outputs, write_outputs


class InventoryFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.json_path = root / "workflow_inventory.json"
        self.markdown_path = root / "workflow_inventory.md"
        self.inventory = {
            "schema_version": "dcoir_workflow_inventory_v1",
            "governing_issue": 194,
            "workflow_count": 0,
            "reusable_workflow_count": 0,
            "composite_action_count": 0,
            "local_reusable_workflow_calls": 0,
            "local_composite_action_calls": 0,
            "contract_registry": ".github/github_actions/workflow_modularization_contracts.json",
            "workflows": [],
        }

    def generate(self) -> None:
        write_outputs(self.inventory, self.json_path, self.markdown_path)

    def check(self) -> list[str]:
        return check_outputs(self.inventory, self.json_path, self.markdown_path)

    def test_exact_generated_outputs_pass(self) -> None:
        self.generate()
        self.assertEqual(self.check(), [])

    def test_missing_both_files_fail_closed(self) -> None:
        findings = self.check()
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("JSON is missing" in s for s in findings))
        self.assertTrue(any("Markdown is missing" in s for s in findings))

    def test_missing_json_is_reported(self) -> None:
        self.generate()
        self.json_path.unlink()
        self.assertTrue(any("JSON is missing" in s for s in self.check()))

    def test_missing_markdown_is_reported(self) -> None:
        self.generate()
        self.markdown_path.unlink()
        self.assertTrue(any("Markdown is missing" in s for s in self.check()))

    def test_mutated_json_is_stale(self) -> None:
        self.generate()
        self.json_path.write_text("{}\n", encoding="utf-8")
        self.assertTrue(any("JSON is stale" in s for s in self.check()))

    def test_mutated_markdown_is_stale(self) -> None:
        self.generate()
        self.markdown_path.write_text("stale\n", encoding="utf-8")
        self.assertTrue(any("Markdown is stale" in s for s in self.check()))

    def test_new_source_counts_make_old_outputs_stale(self) -> None:
        self.generate()
        self.inventory["composite_action_count"] = 1
        findings = self.check()
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("JSON is stale" in s for s in findings))
        self.assertTrue(any("Markdown is stale" in s for s in findings))


if __name__ == "__main__":
    unittest.main()
