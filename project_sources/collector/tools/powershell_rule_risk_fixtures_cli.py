#!/usr/bin/env python3
"""CLI orchestration for rule-risk fixture reporting."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from powershell_rule_risk_fixtures_common import (
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MANIFEST,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_MATRIX,
    DEFAULT_MATRIX_MARKDOWN_OUTPUT,
    RuleRiskFixtureError,
)
from powershell_rule_risk_fixtures_findings import run_fixture_analyzer
from powershell_rule_risk_fixtures_reporting import write_outputs
from powershell_rule_risk_fixtures_runner import build_fixture_report

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DCOIR PowerShell rule-risk fixtures")
    parser.add_argument("--fixture-analyzer", action="store_true", help="Run deterministic fixture analyzer mode")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--matrix", default=DEFAULT_MATRIX.as_posix(), help="Rule-to-risk matrix JSON")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST.as_posix(), help="Fixture manifest JSON")
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix(), help="Fixture report JSON output path")
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix(), help="Fixture report Markdown output path")
    parser.add_argument(
        "--matrix-markdown-output",
        default=DEFAULT_MATRIX_MARKDOWN_OUTPUT.as_posix(),
        help="Generated matrix Markdown output path",
    )
    parser.add_argument("--timeout-seconds", type=int, default=20, help="Analyzer wrapper timeout per fixture")
    parser.add_argument("--no-write", action="store_true", help="Do not write report outputs")
    parser.add_argument(
        "--skip-minimum-risk-class-check",
        action="store_true",
        help="Testing-only escape hatch for small temporary matrices",
    )
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    if args.fixture_analyzer:
        return run_fixture_analyzer()
    report, errors, _warnings, matrix = build_fixture_report(args)
    if not args.no_write:
        try:
            write_outputs(
                Path(args.repo_root).resolve(),
                report,
                matrix,
                Path(args.json_output),
                Path(args.markdown_output),
                Path(args.matrix_markdown_output),
            )
        except RuleRiskFixtureError as exc:
            error = str(exc)
            if error not in errors:
                errors.append(error)
            report["validation"]["success"] = False
            report["validation"]["errors"] = errors
    print(json.dumps(report["summary"], indent=2))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0
