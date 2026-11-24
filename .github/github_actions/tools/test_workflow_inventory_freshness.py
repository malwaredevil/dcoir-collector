#!/usr/bin/env python3
"""Hostile parity tests for the one canonical workflow-inventory freshness check."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lib.workflow_inventory_outputs import check_outputs, write_outputs
from lib.workflow_inventory_core import build_inventory

ROOT = Path(__file__).resolve().parents[3]
MAINTENANCE_WORKFLOW = ROOT / ".github/workflows/reusable-workflow-maintenance-audit.yml"
BUILDER = ROOT / ".github/github_actions/tools/build_workflow_inventory.py"
INVENTORY_COMMAND_RE = re.compile(
    r"(?m)^\s*python3\s+\.github/github_actions/tools/build_workflow_inventory\.py(?:\s+--check)?\s*$"
)


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


class ShippedWorkflowInventoryWiringTests(unittest.TestCase):
    def workflow_text(self) -> str:
        return MAINTENANCE_WORKFLOW.read_text(encoding="utf-8")

    def test_only_read_only_inventory_command_is_executable(self) -> None:
        workflow = self.workflow_text()
        commands = [match.group().strip() for match in INVENTORY_COMMAND_RE.finditer(workflow)]
        self.assertEqual(
            commands,
            ["python3 .github/github_actions/tools/build_workflow_inventory.py --check"],
        )
        self.assertNotIn("      - name: Regenerate workflow inventory", workflow)

    def test_freshness_after_drift_before_contracts(self) -> None:
        workflow = self.workflow_text()
        names = (
            "      - name: Check workflow consistency drift",
            "      - name: Check workflow inventory freshness",
            "      - name: Check workflow modularization contracts",
            "      - name: Check reusable and composite contract posture",
        )
        indices = [workflow.index(name) for name in names]
        self.assertEqual(indices, sorted(indices))
        self.assertIn("if ! git diff --quiet --", workflow)
        self.assertIn(".github/github_actions/workflow_inventory.json", workflow)
        self.assertIn(".github/github_actions/workflow_inventory.md", workflow)


class ShippedInventoryCliTests(unittest.TestCase):
    """Run the actual shipped CLI against disposable output files."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.json_path = root / "workflow_inventory.json"
        self.markdown_path = root / "workflow_inventory.md"
        self.inventory = build_inventory()
        write_outputs(self.inventory, self.json_path, self.markdown_path)

    def run_builder(self, *, check: bool) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable, str(BUILDER),
            "--json-output", str(self.json_path),
            "--markdown-output", str(self.markdown_path),
        ]
        if check:
            command.append("--check")
        return subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True,
            check=False, timeout=90,
        )

    def bytes_or_none(self, path: Path) -> bytes | None:
        return path.read_bytes() if path.exists() else None

    def test_valid_outputs_pass_without_rewrite(self) -> None:
        before = (self.json_path.read_bytes(), self.markdown_path.read_bytes())
        result = self.run_builder(check=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (self.json_path.read_bytes(), self.markdown_path.read_bytes()), before
        )

    def test_missing_single_or_both_outputs_fail_without_repair(self) -> None:
        for missing in ("json", "markdown", "both"):
            with self.subTest(missing=missing):
                write_outputs(self.inventory, self.json_path, self.markdown_path)
                if missing in ("json", "both"):
                    self.json_path.unlink()
                if missing in ("markdown", "both"):
                    self.markdown_path.unlink()
                before = (
                    self.bytes_or_none(self.json_path),
                    self.bytes_or_none(self.markdown_path),
                )
                result = self.run_builder(check=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("is missing", result.stdout + result.stderr)
                self.assertEqual(
                    (self.bytes_or_none(self.json_path), self.bytes_or_none(self.markdown_path)),
                    before,
                )

    def test_stale_single_outputs_fail_without_repair(self) -> None:
        for stale in ("json", "markdown"):
            with self.subTest(stale=stale):
                write_outputs(self.inventory, self.json_path, self.markdown_path)
                path = self.json_path if stale == "json" else self.markdown_path
                path.write_text("deliberately stale\n", encoding="utf-8")
                before = (self.json_path.read_bytes(), self.markdown_path.read_bytes())
                result = self.run_builder(check=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("is stale", result.stdout + result.stderr)
                self.assertEqual(
                    (self.json_path.read_bytes(), self.markdown_path.read_bytes()),
                    before,
                )

    def test_deliberate_maintenance_generation_then_check_succeeds(self) -> None:
        self.json_path.unlink()
        self.markdown_path.unlink()
        generation = self.run_builder(check=False)
        self.assertEqual(generation.returncode, 0, generation.stdout + generation.stderr)
        before = (self.json_path.read_bytes(), self.markdown_path.read_bytes())
        result = self.run_builder(check=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (self.json_path.read_bytes(), self.markdown_path.read_bytes()), before
        )


if __name__ == "__main__":
    unittest.main()
