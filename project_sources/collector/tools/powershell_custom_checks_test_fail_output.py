#!/usr/bin/env python3
"""Fail-row custom-check tests."""
from __future__ import annotations

from pathlib import Path

from powershell_custom_checks_test_common import check_def, custom


class FailOutputCustomCheckMixin:
    def test_fixture_report_passes_and_has_normalized_fields(self) -> None:
        with self.make_repo() as temp:
            report, errors, _warnings = custom.build_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["custom_check_count"], 1)
        self.assertEqual(report["summary"]["negative_fixture_count"], 1)
        self.assertEqual(report["summary"]["control_fixture_count"], 1)
        self.assertEqual(report["summary"]["expected_fixture_finding_count"], 1)
        self.assertEqual(report["summary"]["observed_fixture_finding_count"], 1)
        finding = report["findings"][0]
        for key in ("check_id", "risk_class", "path", "severity", "observed_problem", "impact", "fix"):
            self.assertIn(key, finding)

    def test_bad_fixture_must_trigger(self) -> None:
        with self.make_repo(bad_text='Write-Output "all clear"\n') as temp:
            report, errors, _warnings = custom.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("was not produced" in error for error in errors))

    def test_control_fixture_must_stay_clean(self) -> None:
        with self.make_repo(good_text='$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }\n') as temp:
            report, errors, _warnings = custom.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("control fixture produced unexpected findings" in error for error in errors))

    def test_fail_output_ignores_unrelated_throw_elsewhere(self) -> None:
        text = 'throw "unrelated guard"\n\n$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }\n'
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_fail_output_ignores_unrelated_validation_fail_elsewhere(self) -> None:
        text = '$validation = "FAIL"\n\n$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }\n'
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_fail_output_ignores_status_fail_variable_outside_result_object(self) -> None:
        text = '$Status = "FAIL"\nWrite-Output "not a fixture result row"\n'
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/good/control.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(findings, [])

    def test_fail_output_counts_only_result_object_status_fail(self) -> None:
        text = '$Status = "FAIL"\n\n$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }\n'
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_fail_output_flags_only_unsafe_mixed_rows(self) -> None:
        text = "\n".join(
            [
                '$Rows += [pscustomobject]@{ Check = "Safe"; Status = "FAIL" }',
                'throw "safe row failed closed"',
                "",
                '$Rows += [pscustomobject]@{ Check = "Unsafe"; Status = "FAIL" }',
                "",
                'exit 1',
                "",
            ]
        )
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 4)

    def test_fail_output_ignores_commented_local_failure_action(self) -> None:
        text = "\n".join(
            [
                '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }',
                "# TODO throw when wired",
                "",
            ]
        )
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 1)

    def test_fail_output_ignores_quoted_local_failure_action(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Fixture"',
                '    Status = "FAIL"',
                '    RecommendedFix = "throw when this fails"',
                "}",
                "",
            ]
        )
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_fail_output_accepts_indented_local_failure_actions(self) -> None:
        actions = ['throw "failed"', "exit 1", "return $false"]
        for action in actions:
            with self.subTest(action=action):
                text = "\n".join(
                    [
                        '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }',
                        f"    {action}",
                        "",
                    ]
                )
                findings = custom.check_fail_output(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/good/custom_fail_row_fails_command.ps1",
                    check_def(
                        "dcoir-fail-output-must-fail",
                        "DCOIR.FailOutputMustFailValidation",
                        "fail_rows_reports_or_fixture_outputs_not_causing_failure",
                    ),
                )

                self.assertEqual(findings, [])

    def test_fail_output_ignores_block_comment_failure_action(self) -> None:
        text = "\n".join(
            [
                '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }',
                "<#",
                "throw later",
                "#>",
                "",
            ]
        )
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 1)

    def test_fail_output_ignores_here_string_failure_action(self) -> None:
        text = "\n".join(
            [
                '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }',
                '$message = @"',
                "throw later",
                '"@',
                "",
            ]
        )
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 1)

    def test_fail_output_ignores_non_code_fail_mentions(self) -> None:
        cases = {
            "comment": "# $Rows += [pscustomobject]@{ Check = 'Fixture'; Status = 'FAIL' }",
            "quoted": '$message = "$Rows += [pscustomobject]@{ Check = \'Fixture\'; Status = \'FAIL\' }"',
            "here_string": "\n".join(
                [
                    '$message = @"',
                    "$Rows += [pscustomobject]@{ Check = 'Fixture'; Status = 'FAIL' }",
                    '"@',
                ]
            ),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                findings = custom.check_fail_output(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/good/custom_fail_row_fails_command.ps1",
                    check_def(
                        "dcoir-fail-output-must-fail",
                        "DCOIR.FailOutputMustFailValidation",
                        "fail_rows_reports_or_fixture_outputs_not_causing_failure",
                    ),
                )

                self.assertEqual(findings, [])

    def test_fail_output_does_not_treat_comment_or_string_as_here_string_start(self) -> None:
        cases = {
            "comment_opener": '# docs @"',
            "quoted_opener": '$message = "docs @"',
        }
        for name, opener in cases.items():
            with self.subTest(name=name):
                text = "\n".join(
                    [
                        opener,
                        '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }',
                        "",
                    ]
                )
                findings = custom.check_fail_output(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
                    check_def(
                        "dcoir-fail-output-must-fail",
                        "DCOIR.FailOutputMustFailValidation",
                        "fail_rows_reports_or_fixture_outputs_not_causing_failure",
                    ),
                )

                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["line"], 2)

    def test_fail_output_does_not_treat_comment_or_string_as_block_comment_start(self) -> None:
        cases = {
            "comment_opener": "# docs <#",
            "quoted_opener": '$message = "docs <#"',
        }
        for name, opener in cases.items():
            with self.subTest(name=name):
                text = "\n".join(
                    [
                        opener,
                        '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }',
                        "",
                    ]
                )
                findings = custom.check_fail_output(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
                    check_def(
                        "dcoir-fail-output-must-fail",
                        "DCOIR.FailOutputMustFailValidation",
                        "fail_rows_reports_or_fixture_outputs_not_causing_failure",
                    ),
                )

                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["line"], 2)

    def test_fail_output_tracks_long_pscustomobject_until_closing_brace(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Fixture"',
                '    Scope = "Analyzer"',
                '    Rule = "DCOIR.FailOutputMustFailValidation"',
                '    Target = "fixture"',
                '    Category = "validation"',
                '    Surface = "PowerShell"',
                '    Evidence = "row"',
                '    Detail = "bad row"',
                '    Recommendation = "fail closed"',
                '    Status = "FAIL"',
                '    Extra = "more object content"',
                "}",
                'throw "long object failed closed"',
                "",
            ]
        )
        findings = custom.check_fail_output(
            text,
            "project_sources/collector/fixtures/powershell_analysis/good/custom_fail_row_fails_command.ps1",
            check_def(
                "dcoir-fail-output-must-fail",
                "DCOIR.FailOutputMustFailValidation",
                "fail_rows_reports_or_fixture_outputs_not_causing_failure",
            ),
        )

        self.assertEqual(findings, [])
