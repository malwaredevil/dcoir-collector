#!/usr/bin/env python3
"""Build the #268 PowerShell review-assist report.

This stable entrypoint keeps the workflow and test import surface intact while
the implementation lives in connector-sized helper modules beside it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from powershell_review_assist_builder import build_report, mark_report_write_failure, write_outputs
from powershell_review_assist_common import (
    DEFAULT_ANALYZER_REPORT,
    DEFAULT_ASSEMBLY_PARITY_REPORT,
    DEFAULT_CUSTOM_REPORT,
    DEFAULT_ENGINE_BOUNDARY_REPORT,
    DEFAULT_FUNCTION_REACHABILITY_REPORT,
    DEFAULT_GOVERNANCE_REPORT,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_RULE_RISK_MATRIX,
    DEFAULT_RULE_RISK_REPORT,
    DEFAULT_SCHEMA_PATH,
    DEFAULT_SURFACE_INVENTORY,
    ReviewAssistError,
    SCHEMA_VERSION,
    SCHEMA_VERSIONS,
)
from powershell_review_assist_rendering import (
    render_markdown,
    validate_against_schema_contract,
    validate_markdown_parity,
)

__all__ = (
    "DEFAULT_ANALYZER_REPORT",
    "DEFAULT_ASSEMBLY_PARITY_REPORT",
    "DEFAULT_CUSTOM_REPORT",
    "DEFAULT_ENGINE_BOUNDARY_REPORT",
    "DEFAULT_FUNCTION_REACHABILITY_REPORT",
    "DEFAULT_GOVERNANCE_REPORT",
    "DEFAULT_JSON_OUTPUT",
    "DEFAULT_MARKDOWN_OUTPUT",
    "DEFAULT_RULE_RISK_MATRIX",
    "DEFAULT_RULE_RISK_REPORT",
    "DEFAULT_SCHEMA_PATH",
    "DEFAULT_SURFACE_INVENTORY",
    "ReviewAssistError",
    "SCHEMA_VERSION",
    "SCHEMA_VERSIONS",
    "build_report",
    "mark_report_write_failure",
    "render_markdown",
    "validate_against_schema_contract",
    "validate_markdown_parity",
    "write_outputs",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA_PATH.as_posix(), help="JSON Schema contract path")
    parser.add_argument("--surface-inventory", default=DEFAULT_SURFACE_INVENTORY.as_posix(), help="#261 surface inventory JSON")
    parser.add_argument("--rule-risk-report", default=DEFAULT_RULE_RISK_REPORT.as_posix(), help="#263 rule-risk fixture report JSON")
    parser.add_argument("--rule-risk-matrix", default=DEFAULT_RULE_RISK_MATRIX.as_posix(), help="#263 rule-risk matrix JSON")
    parser.add_argument("--custom-report", default=DEFAULT_CUSTOM_REPORT.as_posix(), help="#264 custom-check report JSON")
    parser.add_argument("--assembly-parity-report", default=DEFAULT_ASSEMBLY_PARITY_REPORT.as_posix(), help="#265 assembly parity report JSON")
    parser.add_argument("--governance-report", default=DEFAULT_GOVERNANCE_REPORT.as_posix(), help="#266 finding governance report JSON")
    parser.add_argument("--engine-boundary-report", default=DEFAULT_ENGINE_BOUNDARY_REPORT.as_posix(), help="#267 engine/Pester boundary report JSON")
    parser.add_argument(
        "--function-reachability-report",
        default=DEFAULT_FUNCTION_REACHABILITY_REPORT.as_posix(),
        help="#306 function reachability report JSON",
    )
    parser.add_argument("--analyzer-report", default=DEFAULT_ANALYZER_REPORT.as_posix(), help="Optional #262 analyzer report JSON")
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix(), help="Output JSON report path")
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix(), help="Output Markdown report path")
    parser.add_argument("--no-write", action="store_true", help="Build the report without writing output files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    report, _errors, _warnings = build_report(args)
    repo_root = Path(args.repo_root).resolve()
    if not args.no_write:
        try:
            write_outputs(repo_root, report, Path(args.json_output), Path(args.markdown_output))
        except ReviewAssistError as exc:
            mark_report_write_failure(report, str(exc))
    if report["validation"]["success"]:
        return 0
    for error in report["validation"]["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
