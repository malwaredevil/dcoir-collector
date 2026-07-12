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


class PowerShellAnalyzerOutputTests(PowerShellAnalyzerTestCase):
    def test_report_write_failure_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report, errors, _warnings = analyzer.build_report(self.make_args(root))
            self.assertEqual(errors, [])
            assert report is not None
            (root / "output-as-directory").mkdir()
            with self.assertRaises(analyzer.AnalyzerContractError) as caught:
                analyzer.write_outputs(root, report, Path("output-as-directory"), Path("report.md"))

        self.assertIn("report write failure", str(caught.exception))

    def test_markdown_report_write_failure_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report, errors, _warnings = analyzer.build_report(self.make_args(root))
            self.assertEqual(errors, [])
            assert report is not None
            (root / "markdown-output-as-directory").mkdir()
            with self.assertRaises(analyzer.AnalyzerContractError) as caught:
                analyzer.write_outputs(root, report, Path("report.json"), Path("markdown-output-as-directory"))

        self.assertIn("report write failure", str(caught.exception))

    def test_report_output_paths_must_stay_inside_repo(self) -> None:
        scenarios = [
            (
                "json traversal",
                Path("../outside-report.json"),
                Path("report.md"),
                "JSON report output path",
                "outside-report.json",
            ),
            (
                "json absolute",
                "ABSOLUTE_JSON",
                Path("report.md"),
                "JSON report output path",
                "outside-report.json",
            ),
            (
                "markdown traversal",
                Path("report.json"),
                Path("../outside-report.md"),
                "Markdown report output path",
                "outside-report.md",
            ),
            (
                "markdown absolute",
                Path("report.json"),
                "ABSOLUTE_MARKDOWN",
                "Markdown report output path",
                "outside-report.md",
            ),
        ]
        for name, json_output, markdown_output, expected_label, outside_name in scenarios:
            with self.subTest(name=name):
                with self.make_repo() as temp:
                    root = Path(temp).resolve()
                    outside = root.parent / outside_name
                    outside.unlink(missing_ok=True)
                    if json_output == "ABSOLUTE_JSON":
                        json_output = outside
                    if markdown_output == "ABSOLUTE_MARKDOWN":
                        markdown_output = outside
                    report, errors, _warnings = analyzer.build_report(self.make_args(root))
                    self.assertEqual(errors, [])
                    assert report is not None
                    with self.assertRaises(analyzer.AnalyzerContractError) as caught:
                        analyzer.write_outputs(root, report, Path(json_output), Path(markdown_output))

                self.assertIn(f"{expected_label} must be a repo-relative path without traversal", str(caught.exception))
                self.assertFalse(outside.exists())

    def test_report_output_paths_must_not_alias(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp).resolve()
            report, errors, _warnings = analyzer.build_report(self.make_args(root))
            self.assertEqual(errors, [])
            assert report is not None
            with self.assertRaises(analyzer.AnalyzerContractError) as caught:
                analyzer.write_outputs(root, report, Path("same-report"), Path("same-report"))

        self.assertIn("JSON and Markdown report output paths must be different", str(caught.exception))

    def test_cli_rewrites_json_as_failed_when_markdown_write_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            (root / "markdown-output-as-directory").mkdir()
            argv = [
                "run_powershell_analyzer.py",
                "--repo-root",
                str(root),
                "--analyzer-command",
                sys.executable,
                "--analyzer-command",
                str(root / "fake_analyzer.py"),
                "--analyzer-command",
                "auto",
                "--json-output",
                "report.json",
                "--markdown-output",
                "markdown-output-as-directory",
            ]
            with unittest.mock.patch.object(sys, "argv", argv):
                rc = analyzer.main()
            written = json.loads((root / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(rc, 1)
        self.assertFalse(written["validation"]["success"])
        self.assertTrue(any("report write failure" in error for error in written["validation"]["errors"]))

    def test_setup_failure_report_can_be_written(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            args = self.make_args(root, analyzer_command=[])
            with unittest.mock.patch.object(analyzer.shutil, "which", return_value=None):
                report, errors, _warnings = analyzer.build_report(args)
            self.assertIsNotNone(report)
            self.assertTrue(any("analyzer tool missing" in error for error in errors))
            assert report is not None
            analyzer.write_outputs(root, report, Path("failure-report.json"), Path("failure-report.md"))
            written = json.loads((root / "failure-report.json").read_text(encoding="utf-8"))

        self.assertFalse(written["validation"]["success"])
        self.assertEqual(written["analyzer"]["name"], "not_run")
        self.assertTrue(any("analyzer tool missing" in error for error in written["validation"]["errors"]))


if __name__ == "__main__":
    unittest.main()
