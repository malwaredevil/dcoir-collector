#!/usr/bin/env python3
"""Compatibility entry point for PowerShell analyzer wrapper tests."""
from __future__ import annotations

import unittest

try:
    from . import test_run_powershell_analyzer_baseline as baseline_tests
    from . import test_run_powershell_analyzer_core as core_tests
    from . import test_run_powershell_analyzer_inventory as inventory_tests
    from . import test_run_powershell_analyzer_outputs as output_tests
    from . import test_run_powershell_analyzer_policy as policy_tests
except ImportError:  # pragma: no cover - direct file execution support
    import test_run_powershell_analyzer_baseline as baseline_tests
    import test_run_powershell_analyzer_core as core_tests
    import test_run_powershell_analyzer_inventory as inventory_tests
    import test_run_powershell_analyzer_outputs as output_tests
    import test_run_powershell_analyzer_policy as policy_tests


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for module in (core_tests, policy_tests, inventory_tests, baseline_tests, output_tests):
        suite.addTests(loader.loadTestsFromModule(module))
    return suite


if __name__ == "__main__":
    unittest.main()
