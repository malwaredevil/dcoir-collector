#!/usr/bin/env python3
"""Hostile regression tests for workflow composite-action count enforcement."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import workflow_files
from lib import workflow_modularization_contract_rules as rules
from lib.workflow_files import iter_action_metadata_files


class CompositeActionCountTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.actions = self.root / "actions"
        self.actions.mkdir()

    def add_action(self, name: str, body: str | None = None) -> None:
        directory = self.actions / name
        directory.mkdir()
        (directory / "action.yml").write_text(
            body or "name: sample\nruns:\n  using: composite\n# Compensating evidence: step outputs\n",
            encoding="utf-8",
        )

    def check(self, claimed: object = 2) -> list[str]:
        findings: list[str] = []
        with patch.object(rules, "ACTION_DIR", self.actions):
            rules.check_composite_actions(findings, {"composite_action_count": claimed})
        return findings

    def test_matching_count_accepts_valid_actions(self) -> None:
        self.add_action("a")
        self.add_action("b")
        self.assertEqual(self.check(), [])

    def test_count_below_actual_rejected(self) -> None:
        self.add_action("a")
        self.add_action("b")
        self.assertTrue(any("is 1, but 2" in f for f in self.check(1)))

    def test_count_above_actual_rejected(self) -> None:
        self.add_action("a")
        self.assertTrue(any("is 2, but 1" in f for f in self.check(2)))

    def test_missing_or_invalid_registry_count_rejected(self) -> None:
        self.add_action("a")
        for invalid in (None, True, False, "1", 1.0, -1):
            with self.subTest(invalid=invalid):
                self.assertTrue(
                    any("non-negative integer" in f for f in self.check(invalid))
                )

    def test_missing_action_directory_fails_closed(self) -> None:
        self.actions.rmdir()
        self.assertTrue(
            any("composite action directory is missing" in f for f in self.check())
        )

    def test_missing_action_metadata_fails_closed(self) -> None:
        (self.actions / "empty-action").mkdir()
        findings = self.check(0)
        self.assertTrue(any("missing action.yml" in f for f in findings))

    def test_only_top_level_action_definitions_count(self) -> None:
        self.add_action("a")
        (self.actions / "notes.txt").write_text("ignored", encoding="utf-8")
        nested = self.actions / "a" / "nested"
        nested.mkdir()
        (nested / "action.yml").write_text("not a top-level action", encoding="utf-8")
        self.assertEqual(self.check(1), [])

    def test_runner_metadata_resolution_matches_inventory(self) -> None:
        body = "name: sample\nruns:\n  using: composite\n# Compensating evidence: step outputs\n"
        yaml_only = self.actions / "yaml-only"
        yaml_only.mkdir()
        (yaml_only / "action.yaml").write_text(body, encoding="utf-8")
        both = self.actions / "both"
        both.mkdir()
        (both / "action.yml").write_text(body, encoding="utf-8")
        (both / "action.yaml").write_text("stale shadowed copy", encoding="utf-8")
        mixed_case = self.actions / "mixed-case"
        mixed_case.mkdir()
        (mixed_case / "ACTION.YML").write_text(body, encoding="utf-8")
        findings = self.check(2)
        self.assertEqual(
            [f for f in findings if "mixed-case" not in f], [],
        )
        self.assertTrue(any("mixed-case:1: composite action directory missing" in f for f in findings))
        # Inventory and the version audit use iter_action_metadata_files; it must
        # select exactly the files the contract count accepted.
        with patch.object(workflow_files, "ACTION_DIR", Path("actions")):
            discovered = iter_action_metadata_files(self.root, top_level_only=True)
        self.assertEqual(
            [path.relative_to(self.actions).as_posix() for path in discovered],
            ["both/action.yml", "yaml-only/action.yaml"],
        )

    def test_existing_safety_checks_are_not_weakend(self) -> None:
        self.add_action(
            "unsafe",
            "runs:\n  using: composite\n# Compensating evidence: noted\n"
            "steps:\n  - run: git push origin main\n  - run: echo secrets.EXAMPLE\n",
        )
        findings = self.check(1)
        self.assertTrue(any("git push" in f for f in findings))
        self.assertTrue(any("secrets.*" in f for f in findings))


if __name__ == "__main__":
    unittest.main()
