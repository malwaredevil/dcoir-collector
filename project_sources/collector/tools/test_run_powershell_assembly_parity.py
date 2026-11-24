#!/usr/bin/env python3
from __future__ import annotations

import unittest

from powershell_assembly_parity_test_core import PowerShellAssemblyParityCoreTests
from powershell_assembly_parity_test_inputs_outputs import PowerShellAssemblyParityInputOutputTests
from powershell_assembly_parity_test_parser import PowerShellAssemblyParityParserTests
from powershell_assembly_parity_test_paths import PowerShellAssemblyParityPathSafetyTests
from powershell_assembly_parity_test_real_repo import PowerShellAssemblyParityRealRepoTests
from powershell_assembly_parity_test_support import parity

__all__ = (
    "PowerShellAssemblyParityCoreTests",
    "PowerShellAssemblyParityInputOutputTests",
    "PowerShellAssemblyParityParserTests",
    "PowerShellAssemblyParityPathSafetyTests",
    "PowerShellAssemblyParityRealRepoTests",
)

_TEST_CASES = (
    PowerShellAssemblyParityCoreTests,
    PowerShellAssemblyParityPathSafetyTests,
    PowerShellAssemblyParityParserTests,
    PowerShellAssemblyParityInputOutputTests,
    PowerShellAssemblyParityRealRepoTests,
)


class PowerShellAssemblyParityEvidenceTests(unittest.TestCase):
    def test_controlled_bad_case_evidence_names_real_tests(self) -> None:
        loader = unittest.TestLoader()
        names = {name for case in _TEST_CASES for name in loader.getTestCaseNames(case)}
        for case in parity.controlled_bad_cases():
            for evidence in case["evidence"].split(" and "):
                with self.subTest(case=case["case"], evidence=evidence):
                    self.assertIn(evidence, names)


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for test_case in (*_TEST_CASES, PowerShellAssemblyParityEvidenceTests):
        suite.addTests(loader.loadTestsFromTestCase(test_case))
    return suite


if __name__ == "__main__":
    raise SystemExit(unittest.main())
