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


class PowerShellAnalyzerCoreTests(PowerShellAnalyzerTestCase):
    def test_control_report_passes_and_records_counts(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = analyzer.build_report(self.make_args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertIsNotNone(report)
        assert report is not None
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["target_count"], 2)
        self.assertEqual(report["summary"]["analyzed_count"], 2)
        self.assertEqual(report["summary"]["skipped_target_count"], 0)
        self.assertEqual(report["summary"]["reference_or_excluded_surface_count"], 1)
        self.assertEqual(report["analyzer"]["name"], "FakePSScriptAnalyzer")
        self.assertEqual(report["powershell"]["version"], "7.4.1")

    def test_windows_separator_target_path_selects_inventory_target(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/source/DCOIR_Collector.ps1"
            requested = rel.replace("/", "\\")
            report, errors, _warnings = analyzer.build_report(
                self.make_args(root, target_path=[requested])
            )

        self.assertEqual(errors, [])
        assert report is not None
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["target_count"], 1)
        self.assertEqual(report["targets"][0]["path"], rel)

    def test_targeted_operator_tooling_surface_does_not_require_primary_surface(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = ".github/scripts/Invoke-ChatGptReportPush.ps1"
            tooling_text = "Write-Output 'tooling ok'\n"
            write(root / rel, tooling_text)
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"].append(
                surface(
                    rel,
                    "operator_tooling",
                    ".ps1",
                    sha256=analyzer.sha256_text(tooling_text),
                )
            )
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root, target_path=[rel]))

        self.assertEqual(errors, [])
        assert report is not None
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["target_count"], 1)
        self.assertEqual(report["targets"][0]["path"], rel)

    def test_ps1_txt_target_is_staged_and_finding_path_maps_back(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1.txt"
            source_part_text = "Write-Host 'bad source part'\n"
            write(root / rel, source_part_text)
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"].append(
                surface(
                    rel,
                    "collector_harness_source_part",
                    ".ps1.txt",
                    sha256=analyzer.sha256_text(source_part_text),
                )
            )
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
            args = self.make_args(root, target_path=[rel], allow_findings=True)
            report, errors, _warnings = analyzer.build_report(args)

        self.assertEqual(errors, [])
        assert report is not None
        self.assertEqual(report["findings"][0]["path"], rel)
        self.assertEqual(report["findings"][0]["rule_name"], "PSAvoidUsingWriteHost")
        self.assertEqual(report["targets"][0]["path"], rel)
        self.assertTrue(report["targets"][0]["staged_for_analysis"])
        self.assertNotIn("absolute_path", report["targets"][0])
        self.assertNotIn("analysis_path", report["targets"][0])

    def test_missing_analyzer_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            args = self.make_args(root, analyzer_command=[str(root / "missing_analyzer")])
            report, errors, _warnings = analyzer.build_report(args)

        self.assertIsNotNone(report)
        self.assertTrue(any("analyzer tool missing" in error for error in errors))

    def test_analyzer_crash_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = analyzer.build_report(self.make_args(Path(temp), "crash"))

        self.assertIsNotNone(report)
        self.assertTrue(any("analyzer crash" in error for error in errors))

    def test_analyzer_timeout_fails_closed(self) -> None:
        with self.make_repo() as temp:
            args = self.make_args(Path(temp), "timeout", timeout_seconds=1)
            report, errors, _warnings = analyzer.build_report(args)

        self.assertIsNotNone(report)
        self.assertTrue(any("analyzer timeout" in error for error in errors))

    def test_skipped_target_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = analyzer.build_report(self.make_args(Path(temp), "skip"))

        self.assertIsNotNone(report)
        self.assertTrue(any("intended analyzer target was skipped" in error for error in errors))

    def test_missing_analyzed_field_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = analyzer.build_report(self.make_args(Path(temp), "missing_analyzed"))

        self.assertIsNotNone(report)
        self.assertTrue(any("intended analyzer target was skipped" in error for error in errors))

    def test_null_analyzed_field_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = analyzer.build_report(self.make_args(Path(temp), "null_analyzed"))

        self.assertIsNotNone(report)
        self.assertTrue(any("intended analyzer target was skipped" in error for error in errors))

    def test_string_analyzed_field_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = analyzer.build_report(self.make_args(Path(temp), "string_analyzed"))

        self.assertIsNotNone(report)
        self.assertTrue(any("intended analyzer target was skipped" in error for error in errors))

    def test_missing_target_path_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = analyzer.build_report(self.make_args(Path(temp), "missing_target_path"))

        self.assertIsNotNone(report)
        self.assertTrue(any("missing target_path" in error for error in errors))

    def test_unsupported_powershell_version_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = analyzer.build_report(self.make_args(Path(temp), "old_version"))

        self.assertIsNotNone(report)
        self.assertTrue(any("unsupported PowerShell version" in error for error in errors))



if __name__ == "__main__":
    unittest.main()
