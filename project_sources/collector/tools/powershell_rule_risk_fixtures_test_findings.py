#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from powershell_rule_risk_fixtures_test_support import RuleRiskFixtureTestCase, harness


class PowerShellRuleRiskFixtureFindingTests(RuleRiskFixtureTestCase):
    def test_fixture_findings_ignore_non_code_skip_success_mentions(self) -> None:
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
                findings = harness.fixture_findings(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/good/control.ps1",
                )

                self.assertFalse(
                    any(finding["rule_name"] == "DCOIR.NoAnalyzerSkipSuccess" for finding in findings)
                )

    def test_fixture_findings_do_not_treat_comment_or_string_as_here_string_start_for_skip_success(self) -> None:
        cases = {
            "comment_opener": '# docs @"',
            "quoted_opener": '$message = "docs @"',
        }
        for name, opener in cases.items():
            with self.subTest(name=name):
                findings = harness.fixture_findings(
                    "\n".join(
                        [
                            opener,
                            '$Rows += [pscustomobject]@{ Check = "Analyzer"; Analyzed = $false; Validation = "success" }',
                            "",
                        ]
                    ),
                    "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
                )
                matching = [finding for finding in findings if finding["rule_name"] == "DCOIR.NoAnalyzerSkipSuccess"]

                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["line"], 2)

    def test_fixture_findings_do_not_treat_comment_or_string_as_block_comment_start_for_skip_success(self) -> None:
        cases = {
            "comment_opener": "# docs <#",
            "quoted_opener": '$message = "docs <#"',
        }
        for name, opener in cases.items():
            with self.subTest(name=name):
                findings = harness.fixture_findings(
                    "\n".join(
                        [
                            opener,
                            '$Rows += [pscustomobject]@{ Check = "Analyzer"; Analyzed = $false; Validation = "success" }',
                            "",
                        ]
                    ),
                    "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
                )
                matching = [finding for finding in findings if finding["rule_name"] == "DCOIR.NoAnalyzerSkipSuccess"]

                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["line"], 2)

    def test_fixture_findings_track_long_skip_success_object_until_closing_brace(self) -> None:
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
                '    Validation = "success"',
                "}",
                'throw "long skip object failed closed"',
                "",
            ]
        )
        findings = harness.fixture_findings(
            text,
            "project_sources/collector/fixtures/powershell_analysis/good/control.ps1",
        )

        self.assertFalse(any(finding["rule_name"] == "DCOIR.NoAnalyzerSkipSuccess" for finding in findings))

    def test_fixture_findings_keep_skip_success_evidence_local(self) -> None:
        text = "\n".join(
            [
                "$Rows += [pscustomobject]@{",
                '    Check = "Safe"',
                "    Analyzed = $false",
                '    Validation = "success"',
                "}",
                'throw "safe row failed closed"',
                "",
                "$Rows += [pscustomobject]@{",
                '    Check = "Unsafe"',
                "    Skipped = $true",
                '    Validation = "success"',
                "}",
                "",
            ]
        )
        findings = harness.fixture_findings(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/analyzer_skip_success.ps1",
        )
        matching = [finding for finding in findings if finding["rule_name"] == "DCOIR.NoAnalyzerSkipSuccess"]

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["line"], 10)

    def test_fixture_findings_ignore_non_code_fail_rows(self) -> None:
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
                findings = harness.fixture_findings(
                    text,
                    "project_sources/collector/fixtures/powershell_analysis/good/control.ps1",
                )

                self.assertFalse(
                    any(finding["rule_name"] == "DCOIR.FailOutputMustFailValidation" for finding in findings)
                )

    def test_fixture_findings_ignore_status_fail_variable_outside_result_object(self) -> None:
        findings = harness.fixture_findings(
            '$Status = "FAIL"\nWrite-Host "bad output"\n',
            "project_sources/collector/fixtures/powershell_analysis/bad/write_host.ps1",
        )
        fail_rows = [finding for finding in findings if finding["rule_name"] == "DCOIR.FailOutputMustFailValidation"]
        write_host = [finding for finding in findings if finding["rule_name"] == "PSAvoidUsingWriteHost"]

        self.assertEqual(fail_rows, [])
        self.assertEqual(len(write_host), 1)
        self.assertEqual(write_host[0]["line"], 2)

    def test_fixture_findings_do_not_treat_comment_or_string_as_here_string_start_for_fail_rows(self) -> None:
        cases = {
            "comment_opener": '# docs @"',
            "quoted_opener": '$message = "docs @"',
        }
        for name, opener in cases.items():
            with self.subTest(name=name):
                findings = harness.fixture_findings(
                    "\n".join(
                        [
                            opener,
                            '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }',
                            "",
                        ]
                    ),
                    "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
                )
                matching = [
                    finding for finding in findings if finding["rule_name"] == "DCOIR.FailOutputMustFailValidation"
                ]

                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["line"], 2)

    def test_fixture_findings_do_not_treat_comment_or_string_as_block_comment_start_for_fail_rows(self) -> None:
        cases = {
            "comment_opener": "# docs <#",
            "quoted_opener": '$message = "docs <#"',
        }
        for name, opener in cases.items():
            with self.subTest(name=name):
                findings = harness.fixture_findings(
                    "\n".join(
                        [
                            opener,
                            '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }',
                            "",
                        ]
                    ),
                    "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
                )
                matching = [
                    finding for finding in findings if finding["rule_name"] == "DCOIR.FailOutputMustFailValidation"
                ]

                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["line"], 2)

    def test_fixture_findings_track_long_fail_object_until_closing_brace(self) -> None:
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
                'throw "long fail object failed closed"',
                "",
            ]
        )
        findings = harness.fixture_findings(
            text,
            "project_sources/collector/fixtures/powershell_analysis/good/control.ps1",
        )

        self.assertFalse(any(finding["rule_name"] == "DCOIR.FailOutputMustFailValidation" for finding in findings))

    def test_fixture_findings_bind_fail_rows_to_local_failure_action(self) -> None:
        text = "\n".join(
            [
                '$Rows += [pscustomobject]@{ Check = "Safe"; Status = "FAIL" }',
                'throw "safe row failed closed"',
                "",
                '$Rows += [pscustomobject]@{ Check = "Unsafe"; Status = "FAIL" }',
                "",
                "exit 1",
                "",
            ]
        )
        findings = harness.fixture_findings(
            text,
            "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1",
        )
        matching = [finding for finding in findings if finding["rule_name"] == "DCOIR.FailOutputMustFailValidation"]

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["line"], 4)

    def test_plaintext_password_fixture_uses_parameter_default_shape(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "fixtures/powershell_analysis/bad/plaintext_password.ps1"
        text = fixture.read_text(encoding="utf-8")

        self.assertRegex(text, r"param\(\[string\]\$Password\s*=")
        findings = harness.fixture_findings(text, fixture.as_posix())
        matching = [
            finding
            for finding in findings
            if finding["rule_name"] == "PSAvoidUsingPlainTextForPassword" and finding["line"] == 2
        ]
        self.assertEqual(len(matching), 1)
