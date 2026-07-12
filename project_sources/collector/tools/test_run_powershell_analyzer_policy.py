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


class PowerShellAnalyzerPolicyTests(PowerShellAnalyzerTestCase):
    def test_missing_policy_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            (root / analyzer.DEFAULT_SETTINGS).unlink()
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("analyzer settings file is missing" in error for error in errors))

    def test_invalid_policy_fails_on_broad_exclusion(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            write(root / analyzer.DEFAULT_SETTINGS, "# DCOIR_POLICY_ID: test\n@{ Severity=@('Information'); ExcludeRules=@('*'); Rules=@{} }\n")
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("wildcard ExcludeRules" in error for error in errors))

    def test_policy_requires_error_and_warning_severities(self) -> None:
        for severity_value in ("@('Error')", "@('Information')", "@('Information', 'Error')"):
            with self.subTest(severity_value=severity_value):
                with self.make_repo() as temp:
                    root = Path(temp)
                    settings = (root / analyzer.DEFAULT_SETTINGS).read_text(encoding="utf-8")
                    settings = settings.replace("Severity = @('Error', 'Warning')", f"Severity = {severity_value}")
                    write(root / analyzer.DEFAULT_SETTINGS, settings)
                    report, errors, _warnings = analyzer.build_report(self.make_args(root))

                self.assertIsNotNone(report)
                self.assertTrue(any("missing active Severity entries" in error for error in errors))

    def test_scalar_wildcard_exclude_rules_fail_closed(self) -> None:
        for excluded in ("'*'", "'PS*'"):
            with self.subTest(excluded=excluded):
                with self.make_repo() as temp:
                    root = Path(temp)
                    settings = (root / analyzer.DEFAULT_SETTINGS).read_text(encoding="utf-8")
                    settings = settings.replace("    Rules = @{", f"    ExcludeRules = {excluded}\n    Rules = @{{")
                    write(root / analyzer.DEFAULT_SETTINGS, settings)
                    report, errors, _warnings = analyzer.build_report(self.make_args(root))

                self.assertIsNotNone(report)
                self.assertTrue(any("ExcludeRules are not allowed" in error for error in errors))

    def test_case_variant_exclude_rules_fail_closed(self) -> None:
        for key, excluded in (("excluderules", "'*'"), ("EXCLUDERULES", "'PS*'")):
            with self.subTest(key=key, excluded=excluded):
                with self.make_repo() as temp:
                    root = Path(temp)
                    settings = (root / analyzer.DEFAULT_SETTINGS).read_text(encoding="utf-8")
                    settings = settings.replace("    Rules = @{", f"    {key} = {excluded}\n    Rules = @{{")
                    write(root / analyzer.DEFAULT_SETTINGS, settings)
                    report, errors, _warnings = analyzer.build_report(self.make_args(root))

                self.assertIsNotNone(report)
                self.assertTrue(any("ExcludeRules are not allowed" in error for error in errors))

    def test_multiline_wildcard_exclude_rules_fail_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            settings = (root / analyzer.DEFAULT_SETTINGS).read_text(encoding="utf-8")
            settings = settings.replace(
                "    Rules = @{",
                "    ExcludeRules = @(\n"
                "        'PS*'\n"
                "    )\n"
                "    Rules = @{",
            )
            write(root / analyzer.DEFAULT_SETTINGS, settings)
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("broad PS* ExcludeRules" in error for error in errors))

    def test_comment_only_required_rules_do_not_satisfy_policy(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            comments = "\n".join(f"# {rule}" for rule in sorted(analyzer.REQUIRED_POLICY_RULES))
            write(
                root / analyzer.DEFAULT_SETTINGS,
                "# DCOIR_POLICY_ID: dcoir-powershell-analyzer-policy-v1\n"
                f"{comments}\n"
                "@{ Severity=@('Error','Warning'); IncludeRules=@(); Rules=@{} }\n",
            )
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("missing active IncludeRules entries" in error for error in errors))
        self.assertTrue(any("missing active Rules keys" in error for error in errors))

    def test_nested_decoy_policy_does_not_satisfy_top_level_policy(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            write(
                root / analyzer.DEFAULT_SETTINGS,
                textwrap.dedent(
                    f"""\
                    # DCOIR_POLICY_ID: dcoir-powershell-analyzer-policy-v1
                    @{{
                        Metadata = @{{
                            Severity = @('Error', 'Warning')
                            IncludeRules = @(
                    {self.required_include_rules_block("            ")}
                            )
                            Rules = @{{
                    {self.required_rule_keys_block("            ")}
                            }}
                            ExcludeRules = @()
                        }}
                        Severity = @('Information')
                        IncludeRules = @()
                        Rules = @{{}}
                        ExcludeRules = @('*')
                    }}
                    """
                ),
            )
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("missing active Severity entries" in error for error in errors))
        self.assertTrue(any("missing active IncludeRules entries" in error for error in errors))
        self.assertTrue(any("missing active Rules keys" in error for error in errors))
        self.assertTrue(any("wildcard ExcludeRules" in error for error in errors))

    def test_duplicate_top_level_policy_assignments_fail_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            settings = (root / analyzer.DEFAULT_SETTINGS).read_text(encoding="utf-8")
            settings = settings.replace(
                "    IncludeRules = @(",
                "    Severity = @('Error', 'Warning')\n    IncludeRules = @(",
            )
            write(root / analyzer.DEFAULT_SETTINGS, settings)
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("duplicate top-level Severity" in error for error in errors))

    def test_case_variant_duplicate_top_level_policy_assignments_fail_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            settings = (root / analyzer.DEFAULT_SETTINGS).read_text(encoding="utf-8")
            settings = settings.replace(
                "    IncludeRules = @(",
                "    severity = @('Error', 'Warning')\n    IncludeRules = @(",
            )
            write(root / analyzer.DEFAULT_SETTINGS, settings)
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("duplicate top-level Severity" in error for error in errors))

    def test_nested_required_rule_names_do_not_satisfy_rules_keys(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            nested_rules = "\n".join(f"            {rule} = @{{}}" for rule in sorted(analyzer.REQUIRED_POLICY_RULES))
            settings = (root / analyzer.DEFAULT_SETTINGS).read_text(encoding="utf-8")
            settings = settings.replace(
                "    Rules = @{\n"
                "        PSAvoidUsingPlainTextForPassword = @{}\n"
                "        PSAvoidUsingConvertToSecureStringWithPlainText = @{}\n"
                "        PSAvoidUsingInvokeExpression = @{}\n"
                "        PSAvoidUsingWriteHost = @{}\n"
                "        PSUseDeclaredVarsMoreThanAssignments = @{}\n"
                "        PSUseShouldProcessForStateChangingFunctions = @{}\n"
                "    }",
                "    Rules = @{\n"
                "        SomeOtherRule = @{\n"
                f"{nested_rules}\n"
                "        }\n"
                "    }",
            )
            write(root / analyzer.DEFAULT_SETTINGS, settings)
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("missing active Rules keys" in error for error in errors))

    def test_policy_requires_rules_assignment_not_only_include_rules(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            write(
                root / analyzer.DEFAULT_SETTINGS,
                textwrap.dedent(
                    """\
                    # DCOIR_POLICY_ID: dcoir-powershell-analyzer-policy-v1
                    @{
                        Severity = @('Error', 'Warning')
                        IncludeRules = @(
                            'PSAvoidUsingPlainTextForPassword'
                            'PSAvoidUsingConvertToSecureStringWithPlainText'
                            'PSAvoidUsingInvokeExpression'
                            'PSAvoidUsingWriteHost'
                            'PSUseDeclaredVarsMoreThanAssignments'
                            'PSUseShouldProcessForStateChangingFunctions'
                        )
                    }
                    """
                ),
            )
            report, errors, _warnings = analyzer.build_report(self.make_args(root))

        self.assertIsNotNone(report)
        self.assertTrue(any("missing Rules declaration" in error for error in errors))



if __name__ == "__main__":
    unittest.main()
