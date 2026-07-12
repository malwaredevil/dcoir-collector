#!/usr/bin/env python3
"""CLI orchestration for custom PowerShell checks."""
from __future__ import annotations

import argparse
import json
import sys

from powershell_custom_checks_common import (
    DEFAULT_CHECKS,
    DEFAULT_FIXTURE_MANIFEST,
    DEFAULT_INVENTORY,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_MATRIX,
)
from powershell_custom_checks_runner import build_report

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DCOIR custom PowerShell checks")
    parser.add_argument("--repo-root", default=".", help="Repository root to scan")
    parser.add_argument("--checks", default=DEFAULT_CHECKS.as_posix(), help="Custom check definition JSON")
    parser.add_argument("--matrix", default=DEFAULT_MATRIX.as_posix(), help="#263 rule-to-risk matrix JSON")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY.as_posix(), help="#261 PowerShell inventory JSON")
    parser.add_argument("--fixture-manifest", default=DEFAULT_FIXTURE_MANIFEST.as_posix(), help="#264 fixture manifest JSON")
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix(), help="Custom check JSON report path")
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix(), help="Custom check Markdown report path")
    parser.add_argument("--target-scope", default="fixtures", choices=["fixtures", "inventory", "all"], help="Targets to scan")
    parser.add_argument("--target-path", action="append", default=[], help="Repo-relative target path to scan; may repeat")
    parser.add_argument("--fail-on-severity", default="Warning", choices=["Information", "Warning", "Error"], help="Finding severity threshold")
    parser.add_argument("--allow-findings", action="store_true", help="Allow non-fixture findings without failing")
    parser.add_argument("--no-write", action="store_true", help="Do not write report outputs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, errors, _warnings = build_report(args)
    print(json.dumps(report["summary"], indent=2))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0
