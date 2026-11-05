#!/usr/bin/env python3
"""Behavior-parity tests for the canonical workflow-file discovery helper."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lib.workflow_files import iter_workflow_files


class WorkflowFileDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workflow_dir = Path(self.temp.name) / "workflows"
        self.workflow_dir.mkdir()

    def add(self, name: str) -> None:
        file = self.workflow_dir / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("name: test\n", encoding="utf-8")

    def test_missing_directory_returns_no_files(self) -> None:
        self.assertEqual(iter_workflow_files(self.workflow_dir / "missing"), [])
        self.assertEqual(iter_workflow_files(self.workflow_dir / "missing", include_reusable=False), [])

    def test_empty_directory_returns_no_files(self) -> None:
        self.assertEqual(iter_workflow_files(self.workflow_dir), [])
        self.assertEqual(iter_workflow_files(self.workflow_dir, include_reusable=False), [])

    def test_yaml_extensions_and_sorted_order(self) -> None:
        for name in ("z.yaml", "b.yml", "a.YAML", "c.txt", "d.yml.bak", "f.YmL"):
            self.add(name)
        expected = ["a.YAML", "b.yml", "f.YmL", "z.yaml"]
        self.assertEqual([p.name for p in iter_workflow_files(self.workflow_dir)], expected)

    def test_primary_excludes_reusable_but_all_includes(self) -> None:
        for name in ("validate.yml", "reusable-build.yml", "reusable-check.yaml", "Reusable-X.yml"):
            self.add(name)
        all_names = [p.name for p in iter_workflow_files(self.workflow_dir)]
        primary = [p.name for p in iter_workflow_files(self.workflow_dir, include_reusable=False)]
        self.assertEqual(all_names, ["Reusable-X.yml", "reusable-build.yml", "reusable-check.yaml", "validate.yml"])
        self.assertEqual(primary, ["Reusable-X.yml", "validate.yml"])

    def test_nested_files_and_directories_are_excluded(self) -> None:
        self.add("top.yml")
        self.add("nested/hidden.yaml")
        (self.workflow_dir / "folder.yml").mkdir()
        self.assertEqual([p.name for p in iter_workflow_files(self.workflow_dir)], ["top.yml"])

    def test_legacy_all_and_primary_semantics_match(self) -> None:
        for name in ("a.yaml", "reusable-1.YAML", "work.yml", "reusable-2.yml", "skip.txt"):
            self.add(name)
        legacy_all = sorted(
            p for p in self.workflow_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
        )
        legacy_primary = sorted(
            p for p in self.workflow_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
            and not p.name.startswith("reusable-")
        )
        self.assertEqual(iter_workflow_files(self.workflow_dir), legacy_all)
        self.assertEqual(iter_workflow_files(self.workflow_dir, include_reusable=False), legacy_primary)


if __name__ == "__main__":
    unittest.main()
