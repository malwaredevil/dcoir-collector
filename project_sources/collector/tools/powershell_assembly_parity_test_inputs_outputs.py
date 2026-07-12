#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from powershell_assembly_parity_test_support import PowerShellAssemblyParityTestCase, parity, write


class PowerShellAssemblyParityInputOutputTests(PowerShellAssemblyParityTestCase):
    def test_baseline_report_path_must_stay_inside_repo_before_read(self) -> None:
        scenarios = [
            ("absolute", "ABSOLUTE_BASELINE"),
            ("traversal", "../outside-baseline.json"),
        ]
        for name, baseline_arg in scenarios:
            with self.subTest(name=name):
                with self.make_repo() as temp:
                    root = Path(temp).resolve()
                    outside = root.parent / "outside-baseline.json"
                    write(outside, "{not-json")
                    if baseline_arg == "ABSOLUTE_BASELINE":
                        baseline_arg = outside.as_posix()
                    report, errors, _warnings = parity.build_report(
                        self.args(root, baseline_report=baseline_arg)
                    )

                self.assertFalse(report["validation"]["success"])
                self.assertTrue(
                    any(
                        "baseline assembly parity report: --baseline-report must be a repo-relative path without traversal"
                        in error
                        for error in errors
                    ),
                    errors,
                )
                self.assertFalse(any("invalid JSON" in error for error in errors), errors)

    def test_cli_input_paths_must_stay_inside_repo_before_read(self) -> None:
        scenarios = [
            ("manifest", "../outside-manifest.json", "collector runtime manifest: --manifest"),
            ("inventory", "../outside-inventory.json", "PowerShell surface inventory: --inventory"),
        ]
        for arg_name, unsafe_path, expected_label in scenarios:
            with self.subTest(arg_name=arg_name):
                with self.make_repo() as temp:
                    root = Path(temp).resolve()
                    report, errors, _warnings = parity.build_report(
                        self.args(root, **{arg_name: unsafe_path})
                    )

                self.assertFalse(report["validation"]["success"])
                self.assertTrue(
                    any(f"{expected_label} must be a repo-relative path without traversal" in error for error in errors),
                    errors,
                )
                self.assertFalse(report[arg_name]["accepted"])

    def test_json_input_directories_fail_closed(self) -> None:
        scenarios = [
            ("manifest", {"manifest": "project_sources/collector"}, "collector runtime manifest could not be read"),
            ("inventory", {"inventory": "project_sources/collector"}, "PowerShell surface inventory could not be read"),
            ("baseline_report", {"baseline_report": "project_sources/collector"}, "baseline assembly parity report could not be read"),
        ]
        for name, overrides, expected_fragment in scenarios:
            with self.subTest(name=name):
                with self.make_repo(checked_in_harness_text='function Invoke-HarnessPart { Write-Output "ok" }\n') as temp:
                    root = Path(temp).resolve()
                    report, errors, _warnings = parity.build_report(
                        self.args(root, **overrides)
                    )

                self.assertFalse(report["validation"]["success"])
                self.assertTrue(any(expected_fragment in error for error in errors), errors)

    def test_output_paths_must_stay_inside_repo_before_write(self) -> None:
        scenarios = [
            (
                "json traversal",
                {"json_output": "../outside-assembly-report.json", "markdown_output": "assembly-report.md"},
                "assembly parity JSON report output: --json-output",
                "outside-assembly-report.json",
            ),
            (
                "json absolute",
                {"json_output": "ABSOLUTE_JSON", "markdown_output": "assembly-report.md"},
                "assembly parity JSON report output: --json-output",
                "outside-assembly-report.json",
            ),
            (
                "markdown traversal",
                {"json_output": "assembly-report.json", "markdown_output": "../outside-assembly-report.md"},
                "assembly parity Markdown report output: --markdown-output",
                "outside-assembly-report.md",
            ),
            (
                "markdown absolute",
                {"json_output": "assembly-report.json", "markdown_output": "ABSOLUTE_MARKDOWN"},
                "assembly parity Markdown report output: --markdown-output",
                "outside-assembly-report.md",
            ),
            (
                "same path",
                {"json_output": "same-report", "markdown_output": "same-report"},
                "assembly parity JSON and Markdown report output paths must be different",
                "same-report",
            ),
        ]
        for name, overrides, expected_label, outside_name in scenarios:
            with self.subTest(name=name):
                with self.make_repo(checked_in_harness_text='function Invoke-HarnessPart { Write-Output "ok" }\n') as temp:
                    root = Path(temp).resolve()
                    outside = root.parent / outside_name
                    outside.unlink(missing_ok=True)
                    if overrides["json_output"] == "ABSOLUTE_JSON":
                        overrides["json_output"] = outside.as_posix()
                    if overrides["markdown_output"] == "ABSOLUTE_MARKDOWN":
                        overrides["markdown_output"] = outside.as_posix()
                    report, errors, _warnings = parity.build_report(
                        self.args(root, no_write=False, **overrides)
                    )

                self.assertFalse(report["validation"]["success"])
                self.assertTrue(
                    any(expected_label in error for error in errors),
                    errors,
                )
                if name != "same path":
                    self.assertFalse(outside.exists())

