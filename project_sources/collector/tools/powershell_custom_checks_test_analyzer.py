#!/usr/bin/env python3
"""Analyzer-skip custom-check tests."""
from __future__ import annotations

from powershell_custom_checks_test_common import check_def, custom


class AnalyzerSkipCustomCheckMixin:
    def test_analyzer_skip_success_ignores_unrelated_throw_elsewhere(self) -> None:
        text = "\n".join(
            [
                'throw "unrelated guard"',
                "",
                "$Rows += [pscustomobject]@{",
                '    Check = "Analyzer"',
                "    Analyzed = $false",
                "    Skipped = $true",
                '    Status = "PASS"',
                "}",
                "",
            ]
        )
        findings = custom.check_analyzer_skip_success(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
            check_def(
                "dcoir-analyzer-skip-success",
                "DCOIR.AnalyzerSkipMustFailClosed",
                "analyzer_or_validation_skip_treated_success",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 5)

    def test_analyzer_skip_success_accepts_local_throw(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Analyzer"',
                "    Analyzed = $false",
                "    Skipped = $true",
                '    Status = "PASS"',
                "}",
                'throw "skip is not allowed"',
                "",
            ]
        )
        findings = custom.check_analyzer_skip_success(
            text,
            "project_sources/collector/fixtures/powershell_analysis/good/custom_analyzer_skip_fails_closed.ps1",
            check_def(
                "dcoir-analyzer-skip-success",
                "DCOIR.AnalyzerSkipMustFailClosed",
                "analyzer_or_validation_skip_treated_success",
            ),
        )

        self.assertEqual(findings, [])

    def test_analyzer_skip_success_ignores_commented_local_failure_action(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Analyzer"',
                "    Analyzed = $false",
                "    Skipped = $true",
                '    Status = "PASS"',
                "}",
                "# TODO exit 1 after wiring",
                "",
            ]
        )
        findings = custom.check_analyzer_skip_success(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
            check_def(
                "dcoir-analyzer-skip-success",
                "DCOIR.AnalyzerSkipMustFailClosed",
                "analyzer_or_validation_skip_treated_success",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_analyzer_skip_success_accepts_indented_local_failure_actions(self) -> None:
        actions = ['throw "skip is not allowed"', "exit 1", "return $false"]
        for action in actions:
            with self.subTest(action=action):
                text = "\n".join(
                    [
                        "$Rows += [pscustomobject]@{",
                        '    Check = "Analyzer"',
                        "    Analyzed = $false",
                        "    Skipped = $true",
                        '    Status = "PASS"',
                        "}",
                        f"    {action}",
                        "",
                    ]
                )
                findings = custom.check_analyzer_skip_success(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/good/custom_analyzer_skip_fails_closed.ps1",
                    check_def(
                        "dcoir-analyzer-skip-success",
                        "DCOIR.AnalyzerSkipMustFailClosed",
                        "analyzer_or_validation_skip_treated_success",
                    ),
                )

                self.assertEqual(findings, [])

    def test_analyzer_skip_success_ignores_block_comment_failure_action(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Analyzer"',
                "    Analyzed = $false",
                "    Skipped = $true",
                '    Status = "PASS"',
                "}",
                "<#",
                "throw later",
                "#>",
                "",
            ]
        )
        findings = custom.check_analyzer_skip_success(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
            check_def(
                "dcoir-analyzer-skip-success",
                "DCOIR.AnalyzerSkipMustFailClosed",
                "analyzer_or_validation_skip_treated_success",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_analyzer_skip_success_ignores_here_string_failure_action(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Analyzer"',
                "    Analyzed = $false",
                "    Skipped = $true",
                '    Status = "PASS"',
                "}",
                '$message = @"',
                "throw later",
                '"@',
                "",
            ]
        )
        findings = custom.check_analyzer_skip_success(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
            check_def(
                "dcoir-analyzer-skip-success",
                "DCOIR.AnalyzerSkipMustFailClosed",
                "analyzer_or_validation_skip_treated_success",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_analyzer_skip_success_ignores_quoted_local_failure_action(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Analyzer"',
                "    Analyzed = $false",
                "    Skipped = $true",
                '    Status = "PASS"',
                '    Message = "throw if skipped"',
                "}",
                "",
            ]
        )
        findings = custom.check_analyzer_skip_success(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
            check_def(
                "dcoir-analyzer-skip-success",
                "DCOIR.AnalyzerSkipMustFailClosed",
                "analyzer_or_validation_skip_treated_success",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_analyzer_skip_success_ignores_non_code_skip_success_mentions(self) -> None:
        cases = {
            "comment": "# Analyzed = $false; Validation = 'success'",
            "quoted": '$message = "Analyzed = $false; Validation = \'success\'"',
            "here_string": "\n".join(
                [
                    '$message = @"',
                    "Analyzed = $false",
                    "Validation = 'success'",
                    '"@',
                ]
            ),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                findings = custom.check_analyzer_skip_success(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/good/custom_analyzer_skip_fails_closed.ps1",
                    check_def(
                        "dcoir-analyzer-skip-success",
                        "DCOIR.AnalyzerSkipMustFailClosed",
                        "analyzer_or_validation_skip_treated_success",
                    ),
                )

                self.assertEqual(findings, [])

    def test_analyzer_skip_success_does_not_treat_comment_or_string_as_here_string_start(self) -> None:
        cases = {
            "comment_opener": '# docs @"',
            "quoted_opener": '$message = "docs @"',
        }
        for name, opener in cases.items():
            with self.subTest(name=name):
                text = "\n".join(
                    [
                        opener,
                        '$Rows += [pscustomobject]@{ Check = "Analyzer"; Analyzed = $false; Status = "PASS" }',
                        "",
                    ]
                )
                findings = custom.check_analyzer_skip_success(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
                    check_def(
                        "dcoir-analyzer-skip-success",
                        "DCOIR.AnalyzerSkipMustFailClosed",
                        "analyzer_or_validation_skip_treated_success",
                    ),
                )

                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["line"], 2)

    def test_analyzer_skip_success_does_not_treat_comment_or_string_as_block_comment_start(self) -> None:
        cases = {
            "comment_opener": "# docs <#",
            "quoted_opener": '$message = "docs <#"',
        }
        for name, opener in cases.items():
            with self.subTest(name=name):
                text = "\n".join(
                    [
                        opener,
                        '$Rows += [pscustomobject]@{ Check = "Analyzer"; Analyzed = $false; Status = "PASS" }',
                        "",
                    ]
                )
                findings = custom.check_analyzer_skip_success(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
                    check_def(
                        "dcoir-analyzer-skip-success",
                        "DCOIR.AnalyzerSkipMustFailClosed",
                        "analyzer_or_validation_skip_treated_success",
                    ),
                )

                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["line"], 2)

    def test_analyzer_skip_success_tracks_long_pscustomobject_until_closing_brace(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Analyzer"',
                '    Scope = "Analyzer"',
                '    Rule = "DCOIR.NoAnalyzerSkipSuccess"',
                '    Target = "fixture"',
                '    Category = "validation"',
                '    Surface = "PowerShell"',
                '    Evidence = "row"',
                '    Detail = "skipped"',
                '    Recommendation = "fail closed"',
                "    Analyzed = $false",
                '    Status = "PASS"',
                "}",
                'throw "long skip object failed closed"',
                "",
            ]
        )
        findings = custom.check_analyzer_skip_success(
            text,
            "project_sources/collector/fixtures/powershell_analysis/good/custom_analyzer_skip_fails_closed.ps1",
            check_def(
                "dcoir-analyzer-skip-success",
                "DCOIR.AnalyzerSkipMustFailClosed",
                "analyzer_or_validation_skip_treated_success",
            ),
        )

        self.assertEqual(findings, [])

    def test_analyzer_skip_success_flags_only_unsafe_mixed_rows(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Safe"',
                "    Analyzed = $false",
                '    Status = "PASS"',
                "}",
                'throw "safe row failed closed"',
                "",
                "$Rows += [pscustomobject]@{",
                '    Check = "Unsafe"',
                "    Skipped = $true",
                '    Status = "PASS"',
                "}",
                "",
                'exit 1',
                "",
            ]
        )
        findings = custom.check_analyzer_skip_success(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
            check_def(
                "dcoir-analyzer-skip-success",
                "DCOIR.AnalyzerSkipMustFailClosed",
                "analyzer_or_validation_skip_treated_success",
            ),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 10)
