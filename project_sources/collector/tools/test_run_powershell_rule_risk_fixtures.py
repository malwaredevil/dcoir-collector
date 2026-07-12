#!/usr/bin/env python3
from __future__ import annotations

import unittest

from powershell_rule_risk_fixtures_test_findings import PowerShellRuleRiskFixtureFindingTests
from powershell_rule_risk_fixtures_test_paths import PowerShellRuleRiskFixturePathSafetyTests
from powershell_rule_risk_fixtures_test_report import PowerShellRuleRiskFixtureReportTests

__all__ = (
    "PowerShellRuleRiskFixtureFindingTests",
    "PowerShellRuleRiskFixturePathSafetyTests",
    "PowerShellRuleRiskFixtureReportTests",
)

_TEST_CASES = (
    PowerShellRuleRiskFixtureFindingTests,
    PowerShellRuleRiskFixturePathSafetyTests,
    PowerShellRuleRiskFixtureReportTests,
)


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for test_case in _TEST_CASES:
        suite.addTests(loader.loadTestsFromTestCase(test_case))
    return suite


if __name__ == "__main__":
    raise SystemExit(unittest.main())
