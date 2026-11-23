#!/usr/bin/env python3
"""Run shipped required-surface regressions in the existing Windows full CI discovery."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / '.github/github_actions/tools'


class RequiredSurfaceGroupedCIValidationTests(unittest.TestCase):
    """Use real regression suites, not duplicated/mirrored validation logic."""

    def run_shipped_suite(self, filename: str) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOLS / filename), '-q'],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_strict_grouped_parser_and_generator(self) -> None:
        self.run_shipped_suite('test_required_surface_profile_groups.py')

    def test_grouped_checker_end_to_end(self) -> None:
        self.run_shipped_suite('test_grouped_checker_integration.py')

    def test_original_checker_and_supplement_regressions(self) -> None:
        self.run_shipped_suite('test_check_required_surfaces.py')


if __name__ == '__main__':
    unittest.main()
