#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import textwrap
import unittest
import unittest.mock
from pathlib import Path

try:
    from .powershell_analyzer_test_support import (
        PowerShellAnalyzerTestCase,
        analyzer,
        surface,
        update_inventory_sha256,
        write,
    )
except ImportError:  # pragma: no cover - direct file execution support
    from powershell_analyzer_test_support import (
        PowerShellAnalyzerTestCase,
        analyzer,
        surface,
        update_inventory_sha256,
        write,
    )


class PowerShellAnalyzerInventoryTests(PowerShellAnalyzerTestCase):
    def test_invalid_inventory_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            write(root / analyzer.DEFAULT_INVENTORY, "{not-json")
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("invalid JSON" in error for error in errors))

    def test_missing_inventory_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            (root / analyzer.DEFAULT_INVENTORY).unlink()
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("PowerShell surface inventory is missing" in error for error in errors))

    def test_absolute_inventory_path_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "/tmp/dcoir-outside.ps1"
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"].append(surface(rel, "collector_runtime_wrapper", ".ps1"))
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory path must be repo-relative" in error for error in errors))

    def test_drive_qualified_inventory_path_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "C:outside/collector.ps1"
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"].append(surface(rel, "collector_runtime_wrapper", ".ps1"))
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory path must be repo-relative" in error for error in errors))

    def test_parent_traversal_inventory_path_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "../outside.ps1"
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"].append(surface(rel, "collector_runtime_wrapper", ".ps1"))
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory path must not contain parent traversal" in error for error in errors))

    def test_ps1_txt_parent_traversal_staging_path_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/harness/source/parts/../../outside.ps1.txt"
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"].append(surface(rel, "collector_harness_source_part", ".ps1.txt"))
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory path must not contain parent traversal" in error for error in errors))

    def test_stale_inventory_hash_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/DCOIR_Collector.ps1"
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"][0]["sha256"] = "0" * 64
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory sha256 does not match current file content" in error for error in errors))

    def test_missing_inventory_hash_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/DCOIR_Collector.ps1"
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"][0]["sha256"] = ""
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory sha256 is missing or invalid" in error for error in errors))

    def test_stale_reference_workflow_inventory_hash_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"][2]["sha256"] = "0" * 64
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory sha256 does not match current file content" in error for error in errors))

    def test_missing_reference_workflow_inventory_hash_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"][2]["sha256"] = ""
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory sha256 is missing or invalid" in error for error in errors))

    def test_stale_reference_workflow_hash_fails_with_target_filter(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/DCOIR_Collector.ps1"
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"][2]["sha256"] = "0" * 64
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertIsNotNone(report)
        self.assertTrue(any("inventory sha256 does not match current file content" in error for error in errors))

    def test_inventory_hash_accepts_line_ending_normalized_match(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/DCOIR_Collector.ps1"
            (root / rel).write_bytes(b"Write-Output 'collector ok'\r\n")
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"][0]["sha256"] = analyzer.sha256_text("Write-Output 'collector ok'\n")
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertIsNotNone(report)
        self.assertEqual(errors, [])

    def test_empty_intended_target_set_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            workflow_text = (root / ".github/workflows/validate-on-pr.yml").read_text(encoding="utf-8")
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"] = [
                surface(
                    ".github/workflows/validate-on-pr.yml",
                    "workflow_embedded_powershell",
                    "workflow_yaml",
                    "reference",
                    sha256=analyzer.sha256_text(workflow_text),
                )
            ]
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("intended target set is empty" in error for error in errors))



if __name__ == "__main__":
    unittest.main()
