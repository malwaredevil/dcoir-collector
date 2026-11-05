#!/usr/bin/env python3
"""Audit issue #194 workflow modularization contracts."""
from __future__ import annotations

import sys
import unittest

from lib.workflow_modularization_contract_rules import run_contract_audit


def print_findings(findings: list[str]) -> None:
    print("Workflow modularization contract audit failed:")
    for finding in findings:
        print(f"- {finding}")


def run_regression_tests() -> bool:
    """Run governed audit-tool regression tests in the existing CI lane."""
    modules = (
        "test_check_required_surfaces",
        "test_workflow_file_discovery",
        "test_workflow_composite_action_count",
        "test_workflow_primary_count_source",
    )
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    return unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite).wasSuccessful()


def main() -> int:
    if not run_regression_tests():
        print("Workflow audit tool regression tests failed.")
        return 1
    findings, workflow_count, contract_count = run_contract_audit()
    if findings:
        print_findings(findings)
        return 1

    print(
        "Workflow modularization contract audit passed for "
        f"{workflow_count} workflow files and "
        f"{contract_count} contracts."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
