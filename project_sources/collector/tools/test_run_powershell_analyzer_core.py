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
    def test_transient_null_reference_retries_and_returns_complete_data(self) -> None:
        import subprocess
        from powershell_analyzer_execution import run_analyzer_command
        failure = subprocess.CompletedProcess(["pwsh"], 1, "", "Object reference not set to an instance of an object")
        success = subprocess.CompletedProcess(["pwsh"], 0, json.dumps({"analyzed": True, "findings": []}), "")
        with unittest.mock.patch("powershell_analyzer_execution.subprocess.run", side_effect=[failure, success]) as call:
            result = run_analyzer_command(["pwsh"], "psscriptanalyzer_pwsh", {"target": {"path": "module.psm1"}}, 5)
        self.assertEqual(call.call_count, 2)
        self.assertTrue(result["analyzed"])
        self.assertEqual(result["command_kind"], "psscriptanalyzer_pwsh")

    def test_repeated_null_reference_still_fails_closed(self) -> None:
        import subprocess
        from powershell_analyzer_execution import run_analyzer_command
        crash = subprocess.CompletedProcess(["pwsh"], 1, "", "Object reference not set to an instance of an object")
        with unittest.mock.patch("powershell_analyzer_execution.subprocess.run", return_value=crash) as call:
            with self.assertRaisesRegex(analyzer.AnalyzerContractError, "analyzer crash"):
                run_analyzer_command(["pwsh"], "psscriptanalyzer_pwsh", {"target": {"path": "module.psm1"}}, 5)
        self.assertEqual(call.call_count, 3)

    def test_unrelated_analyzer_failure_does_not_retry(self) -> None:
        import subprocess
        from powershell_analyzer_execution import run_analyzer_command
        crash = subprocess.CompletedProcess(["pwsh"], 9, "", "Other analyzer failure")
        with unittest.mock.patch("powershell_analyzer_execution.subprocess.run", return_value=crash) as call:
            with self.assertRaisesRegex(analyzer.AnalyzerContractError, "Other analyzer failure"):
                run_analyzer_command(["pwsh"], "psscriptanalyzer_pwsh", {"target": {"path": "module.psm1"}}, 5)
        self.assertEqual(call.call_count, 1)
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

    def test_non_policy_legacy_warning_is_reported_without_becoming_blocking(self) -> None:
        with self.make_repo() as temp:
            report, errors, _ = analyzer.build_report(self.make_args(Path(temp), "legacy_warning"))
        self.assertEqual(errors, [])
        assert report is not None
        self.assertEqual(report["summary"]["warning_count"], 2)
        self.assertEqual(report["summary"]["policy_warning_count"], 0)
        self.assertEqual(report["summary"]["blocking_finding_count"], 0)
        self.assertEqual(len(report["findings"]), 2)

    def test_legacy_error_still_blocks_even_when_outside_policy_rules(self) -> None:
        with self.make_repo() as temp:
            report, errors, _ = analyzer.build_report(self.make_args(Path(temp), "legacy_error"))
        self.assertTrue(any("unsuppressed analyzer findings" in e for e in errors))
        assert report is not None
        self.assertEqual(report["summary"]["error_count"], 2)
        self.assertEqual(report["summary"]["blocking_finding_count"], 2)

    def test_parser_error_in_regular_source_fails_closed_even_with_allow_findings(self) -> None:
        with self.make_repo() as temp:
            report, errors, _ = analyzer.build_report(
                self.make_args(Path(temp), "parse_error", allow_findings=True)
            )
        assert report is not None
        self.assertTrue(any("parse errors outside" in e for e in errors), errors)
        self.assertEqual(report["summary"]["parse_error_count"], 2)
        self.assertEqual(report["summary"]["harness_fragment_parse_error_count"], 0)

    def test_unrecognized_severity_fails_closed(self) -> None:
        with self.make_repo() as temp:
            report, errors, _ = analyzer.build_report(
                self.make_args(Path(temp), "unknown_severity", allow_findings=True)
            )
        assert report is not None
        self.assertTrue(any("unknown severity" in e for e in errors), errors)
        self.assertEqual(report["summary"]["unexpected_severity_count"], 2)

    def test_fragment_parse_error_is_classified_not_silently_hidden(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            rel = "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1"
            source = "Write-Output 'split source not assembled here'\n"
            write(root / rel, source)
            inventory = json.loads((root / analyzer.DEFAULT_INVENTORY).read_text(encoding="utf-8"))
            inventory["surfaces"].append(surface(rel, "collector_harness_source_part", ".ps1", sha256=analyzer.sha256_text(source)))
            write(root / analyzer.DEFAULT_INVENTORY, json.dumps(inventory))
            report, errors, _ = analyzer.build_report(self.make_args(root, "harness_fragment_parse"))
        self.assertEqual(errors, [])
        assert report is not None
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["parse_error_count"], 1)
        self.assertEqual(report["summary"]["harness_fragment_parse_error_count"], 1)

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
