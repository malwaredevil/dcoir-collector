#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import unittest.mock
from pathlib import Path

from powershell_rule_risk_fixtures_test_support import RuleRiskFixtureTestCase, harness, write


class PowerShellRuleRiskFixtureReportTests(RuleRiskFixtureTestCase):
    def test_fixture_report_passes_for_negative_and_control(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["negative_fixture_count"], 1)
        self.assertEqual(report["summary"]["control_fixture_count"], 1)
        self.assertEqual(report["summary"]["expected_finding_count"], 1)
        self.assertEqual(report["summary"]["observed_finding_count"], 1)

    def test_fixture_report_ignores_status_fail_variable_outside_result_object(self) -> None:
        with self.make_repo(
            bad_text='$Status = "FAIL"\nWrite-Host "bad output"\n',
            expected_line=2,
        ) as temp:
            report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["expected_finding_count"], 1)
        self.assertEqual(report["summary"]["observed_finding_count"], 1)
        self.assertEqual(report["findings"][0]["rule_name"], "PSAvoidUsingWriteHost")

    def test_temp_inventory_path_passed_repo_relative_to_wrapper(self) -> None:
        captured: dict[str, str] = {}

        def fake_build_report(args: argparse.Namespace) -> tuple[dict[str, object], list[str], list[str]]:
            captured["inventory"] = args.inventory
            return (
                {
                    "schema_version": harness.analyzer.SCHEMA_VERSION,
                    "findings": [
                        {
                            "path": "project_sources/collector/fixtures/powershell_analysis/bad/write_host.ps1",
                            "line": 1,
                            "column": 1,
                            "symbol": "",
                            "rule_name": "PSAvoidUsingWriteHost",
                            "severity": "Warning",
                            "observed_problem": "host output",
                            "recommended_fix": "use durable output",
                        }
                    ],
                },
                [],
                [],
            )

        with self.make_repo() as temp:
            root = Path(temp)
            with unittest.mock.patch.object(harness.analyzer, "build_report", side_effect=fake_build_report):
                report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(root))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertIn("inventory", captured)
        self.assertFalse(Path(captured["inventory"]).is_absolute())
        self.assertTrue(captured["inventory"].startswith(".dcoir-rule-risk-fixtures-"))

    def test_fixture_report_accepts_crlf_fixture_inventory_hashes(self) -> None:
        with self.make_repo(
            bad_text='Write-Host "bad output"\r\n',
            control_text='Write-Output "good output"\r\n',
        ) as temp:
            report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["observed_finding_count"], 1)

    def test_missing_negative_expected_finding_fails(self) -> None:
        with self.make_repo(expected_line=2) as temp:
            report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("expected PSAvoidUsingWriteHost" in error for error in errors))

    def test_control_fixture_unexpected_finding_fails(self) -> None:
        with self.make_repo(control_text='Write-Host "unexpected host output"\n') as temp:
            report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("control fixture produced unexpected findings" in error for error in errors))

    def test_blocking_check_without_fixture_fails(self) -> None:
        with self.make_repo(matrix_fixtures=[]) as temp:
            report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("blocking checks must name at least one fixture" in error for error in errors))

    def test_duplicate_check_id_fails(self) -> None:
        with self.make_repo(duplicate_check=True) as temp:
            report, errors, _warnings, _matrix = harness.build_fixture_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("duplicate check id" in error for error in errors))

    def test_matrix_and_manifest_paths_reject_absolute_and_traversal_before_read(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            outside = root.parent / f"{root.name}-outside-rule-risk-input.json"
            write(outside, "{not-json\n")
            try:
                cases = [
                    ("matrix", outside.as_posix(), "rule-to-risk matrix path"),
                    ("matrix", f"../{outside.name}", "rule-to-risk matrix path"),
                    ("manifest", outside.as_posix(), "fixture manifest path"),
                    ("manifest", f"../{outside.name}", "fixture manifest path"),
                ]
                for attr, value, label in cases:
                    with self.subTest(attr=attr, value=value):
                        args = self.args(root)
                        setattr(args, attr, value)
                        report, errors, _warnings, _matrix = harness.build_fixture_report(args)

                    self.assertFalse(report["validation"]["success"])
                    self.assertTrue(
                        any(f"{label} must be a repo-relative path without traversal" in error for error in errors)
                    )
                    self.assertFalse(any("invalid JSON" in error for error in errors))
            finally:
                outside.unlink(missing_ok=True)

    def test_output_paths_reject_absolute_and_traversal_before_write(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report, errors, _warnings, matrix = harness.build_fixture_report(self.args(root))
            self.assertEqual(errors, [])
            outside = root.parent / f"{root.name}-outside-rule-risk-output.json"
            cases = [
                (
                    Path(f"../{outside.name}"),
                    Path("project_sources/collector/safe-report.md"),
                    Path("project_sources/collector/safe-matrix.md"),
                    "fixture report JSON output path",
                ),
                (
                    Path("project_sources/collector/safe-report.json"),
                    outside,
                    Path("project_sources/collector/safe-matrix.md"),
                    "fixture report Markdown output path",
                ),
                (
                    Path("project_sources/collector/safe-report.json"),
                    Path("project_sources/collector/safe-report.md"),
                    Path(f"../{outside.name}"),
                    "rule-risk matrix Markdown output path",
                ),
            ]
            for json_output, markdown_output, matrix_output, label in cases:
                with self.subTest(label=label):
                    with self.assertRaises(harness.RuleRiskFixtureError) as caught:
                        harness.write_outputs(root, report, matrix, json_output, markdown_output, matrix_output)
                    self.assertIn(label, str(caught.exception))
                    self.assertFalse(outside.exists())

    def test_output_symlink_resolving_outside_repo_is_rejected(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report, errors, _warnings, matrix = harness.build_fixture_report(self.args(root))
            self.assertEqual(errors, [])
            outside_dir = root.parent / f"{root.name}-outside-rule-risk-output-dir"
            outside_dir.mkdir(exist_ok=True)
            link = root / "project_sources/collector/linked-output"
            try:
                link.symlink_to(outside_dir, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            try:
                with self.assertRaises(harness.RuleRiskFixtureError) as caught:
                    harness.write_outputs(
                        root,
                        report,
                        matrix,
                        Path("project_sources/collector/linked-output/report.json"),
                        Path("project_sources/collector/safe-report.md"),
                        Path("project_sources/collector/safe-matrix.md"),
                    )
                self.assertIn("must resolve inside the repository root", str(caught.exception))
                self.assertFalse((outside_dir / "report.json").exists())
            finally:
                (outside_dir / "report.json").unlink(missing_ok=True)
                shutil.rmtree(outside_dir, ignore_errors=True)

    def test_output_paths_must_be_distinct(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            report, errors, _warnings, matrix = harness.build_fixture_report(self.args(root))
            self.assertEqual(errors, [])
            with self.assertRaises(harness.RuleRiskFixtureError) as caught:
                harness.write_outputs(
                    root,
                    report,
                    matrix,
                    Path("project_sources/collector/same-output.md"),
                    Path("project_sources/collector/same-output.md"),
                    Path("project_sources/collector/safe-matrix.md"),
                )

        self.assertIn("must be different", str(caught.exception))

    def test_main_rewrites_json_report_failed_when_later_output_write_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            blocked_markdown = root / "project_sources/collector/blocked-report.md"
            blocked_markdown.mkdir()
            json_output = Path("project_sources/collector/stale-success-report.json")
            argv = [
                "run_powershell_rule_risk_fixtures.py",
                "--repo-root",
                root.as_posix(),
                "--skip-minimum-risk-class-check",
                "--json-output",
                json_output.as_posix(),
                "--markdown-output",
                "project_sources/collector/blocked-report.md",
                "--matrix-markdown-output",
                "project_sources/collector/stale-success-matrix.md",
            ]
            with unittest.mock.patch.object(sys, "argv", argv):
                exit_code = harness.main()
            written = json.loads((root / json_output).read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertFalse(written["validation"]["success"])
        self.assertTrue(any("report write failure" in error for error in written["validation"]["errors"]))

    def test_main_rewrites_status_reports_failed_when_matrix_output_write_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            blocked_matrix = root / "project_sources/collector/blocked-matrix.md"
            blocked_matrix.mkdir()
            json_output = Path("project_sources/collector/matrix-failure-report.json")
            markdown_output = Path("project_sources/collector/matrix-failure-report.md")
            write(root / json_output, json.dumps({"validation": {"success": True}}) + "\n")
            write(root / markdown_output, "# Old Report\n\n- Validation: `pass`\n")
            argv = [
                "run_powershell_rule_risk_fixtures.py",
                "--repo-root",
                root.as_posix(),
                "--skip-minimum-risk-class-check",
                "--json-output",
                json_output.as_posix(),
                "--markdown-output",
                markdown_output.as_posix(),
                "--matrix-markdown-output",
                "project_sources/collector/blocked-matrix.md",
            ]
            with unittest.mock.patch.object(sys, "argv", argv):
                exit_code = harness.main()
            written_json = json.loads((root / json_output).read_text(encoding="utf-8"))
            written_markdown = (root / markdown_output).read_text(encoding="utf-8")

        self.assertEqual(exit_code, 1)
        self.assertFalse(written_json["validation"]["success"])
        self.assertTrue(any("report write failure" in error for error in written_json["validation"]["errors"]))
        self.assertIn("Validation: `fail`", written_markdown)
        self.assertNotIn("Validation: `pass`", written_markdown)
