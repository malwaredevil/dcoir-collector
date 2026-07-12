#!/usr/bin/env python3
"""Validate the #267 PowerShell engine and Pester evidence boundary.

The workflow-facing CLI and compatibility import surface stay in this file;
implementation lives in connector-sized helper modules next to it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import powershell_engine_pester_boundary_contract as _contract
import powershell_engine_pester_boundary_reporting as _reporting
import powershell_engine_pester_boundary_validation as _validation

SCHEMA_VERSION = _contract.SCHEMA_VERSION
BOUNDARY_SCHEMA_VERSION = _contract.BOUNDARY_SCHEMA_VERSION
ISSUE_NUMBER = _contract.ISSUE_NUMBER
PARENT_ISSUE_NUMBER = _contract.PARENT_ISSUE_NUMBER
DEFAULT_BOUNDARY = _contract.DEFAULT_BOUNDARY
DEFAULT_JSON_OUTPUT = _contract.DEFAULT_JSON_OUTPUT
DEFAULT_MARKDOWN_OUTPUT = _contract.DEFAULT_MARKDOWN_OUTPUT
DEFAULT_RULE_RISK_REPORT = _contract.DEFAULT_RULE_RISK_REPORT
DEFAULT_CUSTOM_REPORT = _contract.DEFAULT_CUSTOM_REPORT
DEFAULT_GOVERNANCE_REPORT = _contract.DEFAULT_GOVERNANCE_REPORT
DEFAULT_ASSEMBLY_REPORT = _contract.DEFAULT_ASSEMBLY_REPORT
REQUIRED_CHECK_CATEGORIES = _contract.REQUIRED_CHECK_CATEGORIES
REQUIRED_MATRIX_FIELDS = _contract.REQUIRED_MATRIX_FIELDS
PESTER_EVIDENCE_FIELDS = _contract.PESTER_EVIDENCE_FIELDS
REPORT_SCHEMAS = _contract.REPORT_SCHEMAS
REPO_ARTIFACT_PREFIXES = _contract.REPO_ARTIFACT_PREFIXES
EXPLICIT_ARTIFACT_STATUSES = _contract.EXPLICIT_ARTIFACT_STATUSES
EngineBoundaryError = _contract.EngineBoundaryError
artifact_slash_path = _contract.artifact_slash_path
is_repo_artifact_path = _contract.is_repo_artifact_path
is_windows_drive_path = _contract.is_windows_drive_path
read_json = _contract.read_json
report_finding_count = _contract.report_finding_count
report_success = _contract.report_success
report_success_state = _contract.report_success_state
resolve_repo_artifact_path = _contract.resolve_repo_artifact_path
resolve_repo_input_path = _contract.resolve_repo_input_path
safe_repo_path = _contract.safe_repo_path
scalar = _contract.scalar
summary_count = _contract.summary_count
write_json = _contract.write_json
build_markdown = _reporting.build_markdown
build_report = _reporting.build_report
write_outputs = _reporting.write_outputs
declared_output_artifacts = _validation.declared_output_artifacts
fail_if_missing_fields = _validation.fail_if_missing_fields
has_text = _validation.has_text
validate_boundary_doc = _validation.validate_boundary_doc
validate_source_reports = _validation.validate_source_reports


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--boundary", default=DEFAULT_BOUNDARY.as_posix())
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix())
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix())
    parser.add_argument(
        "--extra-report",
        action="append",
        default=[DEFAULT_ASSEMBLY_REPORT.as_posix()],
        help="Additional dependency report to read and summarize.",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report, errors, _warnings = build_report(args)
    repo_root = Path(args.repo_root).resolve()
    if not args.no_write:
        output_errors = write_outputs(repo_root, report, Path(args.json_output), Path(args.markdown_output))
        if output_errors:
            errors.extend(output_errors)
            report["validation"]["success"] = False
            report["validation"]["errors"] = errors
            rewrite_errors = write_outputs(repo_root, report, Path(args.json_output), Path(args.markdown_output))
            for error in rewrite_errors:
                if error not in errors:
                    errors.append(error)
            report["validation"]["errors"] = errors
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "schema_version": report["schema_version"],
                "matrix_row_count": report["summary"]["matrix_row_count"],
                "required_category_count": report["summary"]["required_category_count"],
                "dependency_report_count": report["summary"]["dependency_report_count"],
                "missing_blocking_output_artifact_count": report["summary"][
                    "missing_blocking_output_artifact_count"
                ],
                "unclaimed_blocking_output_artifact_count": report["summary"][
                    "unclaimed_blocking_output_artifact_count"
                ],
                "rule_risk_fixture_findings": report["independent_analyzer_enforcement_proof"][
                    "rule_risk_fixture_findings"
                ],
                "custom_check_findings": report["independent_analyzer_enforcement_proof"][
                    "custom_check_findings"
                ],
                "governance_classified_findings": report["independent_analyzer_enforcement_proof"][
                    "governance_classified_findings"
                ],
                "pester_blocking_for_static_validation": report["summary"][
                    "pester_blocking_for_static_validation"
                ],
                "success": report["validation"]["success"],
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "BOUNDARY_SCHEMA_VERSION",
    "DEFAULT_ASSEMBLY_REPORT",
    "DEFAULT_BOUNDARY",
    "DEFAULT_CUSTOM_REPORT",
    "DEFAULT_GOVERNANCE_REPORT",
    "DEFAULT_JSON_OUTPUT",
    "DEFAULT_MARKDOWN_OUTPUT",
    "DEFAULT_RULE_RISK_REPORT",
    "EngineBoundaryError",
    "EXPLICIT_ARTIFACT_STATUSES",
    "ISSUE_NUMBER",
    "PARENT_ISSUE_NUMBER",
    "PESTER_EVIDENCE_FIELDS",
    "REPORT_SCHEMAS",
    "REPO_ARTIFACT_PREFIXES",
    "REQUIRED_CHECK_CATEGORIES",
    "REQUIRED_MATRIX_FIELDS",
    "SCHEMA_VERSION",
    "artifact_slash_path",
    "build_markdown",
    "build_report",
    "declared_output_artifacts",
    "fail_if_missing_fields",
    "has_text",
    "is_repo_artifact_path",
    "is_windows_drive_path",
    "main",
    "parse_args",
    "read_json",
    "report_finding_count",
    "report_success",
    "report_success_state",
    "resolve_repo_artifact_path",
    "resolve_repo_input_path",
    "safe_repo_path",
    "scalar",
    "summary_count",
    "validate_boundary_doc",
    "validate_source_reports",
    "write_json",
    "write_outputs",
]


if __name__ == "__main__":
    raise SystemExit(main())
