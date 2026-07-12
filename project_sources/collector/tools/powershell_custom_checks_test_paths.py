#!/usr/bin/env python3
"""Path-safety and real-contract custom-check tests."""
from __future__ import annotations

import json
from pathlib import Path

from powershell_custom_checks_test_common import custom, surface, write


class PathSafetyAndContractCustomCheckMixin:
    def test_target_path_limits_fixture_assertions_to_selected_fixture(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            bad_path = "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1"
            report, errors, _warnings = custom.build_report(
                self.args(root, target_path=[bad_path])
            )

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["targets"], [bad_path])
        self.assertEqual([fixture["id"] for fixture in report["fixtures"]], ["bad-fail-row-green-exit"])
        self.assertEqual(report["summary"]["negative_fixture_count"], 1)
        self.assertEqual(report["summary"]["control_fixture_count"], 0)
        self.assertEqual(report["summary"]["expected_fixture_finding_count"], 1)
        self.assertEqual(report["summary"]["observed_fixture_finding_count"], 1)

    def test_missing_fixture_from_inventory_fails_closed(self) -> None:
        with self.make_repo(omit_good_from_inventory=True) as temp:
            report, errors, _warnings = custom.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("missing from PowerShell surface inventory" in error for error in errors))

    def test_matrix_mapping_mismatch_fails_closed(self) -> None:
        with self.make_repo(matrix_rule_name="DCOIR.OtherRule") as temp:
            report, errors, _warnings = custom.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("rule_name does not match #263 matrix" in error for error in errors))

    def test_missing_input_file_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            (root / custom.DEFAULT_CHECKS).unlink()
            report, errors, _warnings = custom.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("custom checks missing" in error for error in errors))

    def test_cli_input_paths_must_stay_inside_repo_before_read(self) -> None:
        scenarios = [
            ("checks", "ABSOLUTE_CHECKS", "custom checks path", "checks"),
            ("matrix", "../outside-matrix.json", "rule-to-risk matrix path", "matrix"),
            ("inventory", "../outside-inventory.json", "PowerShell surface inventory path", "inventory"),
            ("fixture_manifest", "ABSOLUTE_FIXTURE_MANIFEST", "custom fixture manifest path", "fixture_manifest"),
        ]
        for arg_name, unsafe_path, expected_label, report_key in scenarios:
            with self.subTest(arg_name=arg_name):
                with self.make_repo() as temp:
                    root = Path(temp).resolve()
                    outside_name = "outside-custom-check-input.json"
                    if unsafe_path.startswith("../"):
                        outside_name = unsafe_path.removeprefix("../")
                    outside = root.parent / outside_name
                    write(outside, "{not-json")
                    if unsafe_path.startswith("ABSOLUTE_"):
                        unsafe_path = outside.as_posix()
                    report, errors, _warnings = custom.build_report(
                        self.args(root, **{arg_name: unsafe_path})
                    )

                self.assertFalse(report["validation"]["success"])
                self.assertTrue(
                    any(f"{expected_label} must be a repo-relative path without traversal" in error for error in errors),
                    errors,
                )
                self.assertFalse(any("not valid JSON" in error for error in errors), errors)
                self.assertFalse(report[report_key]["accepted"])

    def test_output_paths_must_stay_inside_repo_before_write(self) -> None:
        scenarios = [
            (
                "json traversal",
                {"json_output": "../outside-custom-report.json", "markdown_output": "custom-report.md"},
                "custom checks JSON report output path",
                "outside-custom-report.json",
            ),
            (
                "markdown absolute",
                {"json_output": "custom-report.json", "markdown_output": "ABSOLUTE_MARKDOWN"},
                "custom checks Markdown report output path",
                "outside-custom-report.md",
            ),
            (
                "same path",
                {"json_output": "same-report", "markdown_output": "same-report"},
                "custom checks JSON and Markdown report output paths must be different",
                "same-report",
            ),
        ]
        for name, overrides, expected_label, outside_name in scenarios:
            with self.subTest(name=name):
                with self.make_repo() as temp:
                    root = Path(temp).resolve()
                    outside = root.parent / outside_name
                    outside.unlink(missing_ok=True)
                    if overrides["markdown_output"] == "ABSOLUTE_MARKDOWN":
                        overrides["markdown_output"] = outside.as_posix()
                    report, errors, _warnings = custom.build_report(
                        self.args(root, no_write=False, **overrides)
                    )

                self.assertFalse(report["validation"]["success"])
                self.assertTrue(
                    any(expected_label in error for error in errors),
                    errors,
                )
                if name != "same path":
                    self.assertFalse(outside.exists())

    def test_inventory_targets_must_be_safe_before_reading(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp).resolve()
            outside = root.parent / "outside_custom_check.ps1"
            write(outside, '$Rows += [pscustomobject]@{ Check = "Outside"; Status = "FAIL" }\n')
            inventory_path = root / custom.DEFAULT_INVENTORY
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["surfaces"].extend([
                surface(outside.as_posix()),
                surface("../outside_custom_check.ps1"),
                surface("C:outside/custom_check.ps1"),
            ])
            inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
            report, errors, _warnings = custom.build_report(self.args(root, target_scope="inventory"))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("path must be a repo-relative path without traversal" in error for error in errors), errors)

    def test_symlinked_inventory_target_fails_before_reading(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp).resolve()
            outside = root.parent / "outside_custom_check_symlink.ps1"
            write(outside, '$Rows += [pscustomobject]@{ Check = "Outside"; Status = "FAIL" }\n')
            rel = "project_sources/collector/fixtures/powershell_analysis/bad/symlink_escape.ps1"
            link = root / rel
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            inventory_path = root / custom.DEFAULT_INVENTORY
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["surfaces"].append(surface(rel))
            inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
            report, errors, _warnings = custom.build_report(self.args(root, target_scope="inventory"))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("path must resolve inside the repository root" in error for error in errors), errors)

    def test_real_custom_contract_has_negative_and_control_for_each_check(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        report, errors, _warnings = custom.build_report(self.args(repo_root))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["custom_check_count"], 8)
        self.assertEqual(report["summary"]["negative_fixture_count"], 8)
        self.assertEqual(report["summary"]["control_fixture_count"], 8)
        self.assertEqual(report["summary"]["expected_fixture_finding_count"], 8)
        self.assertEqual(report["summary"]["observed_fixture_finding_count"], 8)
