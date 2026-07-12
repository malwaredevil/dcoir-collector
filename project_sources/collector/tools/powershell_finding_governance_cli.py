#!/usr/bin/env python3
"""CLI orchestration for PowerShell finding governance."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

from powershell_finding_governance_classification import classify_findings, governance_summary
from powershell_finding_governance_common import (
    DEFAULT_ANALYZER_REPORT,
    DEFAULT_ASSEMBLY_PARITY_REPORT,
    DEFAULT_CUSTOM_REPORT,
    DEFAULT_GOVERNANCE,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_RULE_RISK_REPORT,
    ISSUE_NUMBER,
    SCHEMA_VERSION,
    GovernanceError,
    mark_report_write_failure,
    normalize_date,
)
from powershell_finding_governance_reporting import write_outputs
from powershell_finding_governance_sources import (
    collect_findings,
    generated_output_paths,
    load_doc,
    load_optional_doc,
    report_validation_success_state,
    validate_assembly_parity_report,
)
from powershell_finding_governance_validation import validate_governance_doc


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[str]]:
    repo_root = Path(args.repo_root).resolve()
    today = normalize_date(args.as_of_date) if getattr(args, "as_of_date", "") else date.today()
    if today is None:
        today = date.today()
    errors: list[str] = []
    warnings: list[str] = []
    governance: dict[str, Any] = {}
    assembly_report: dict[str, Any] | None = None
    assembly_report_for_coverage: dict[str, Any] | None = None
    try:
        governance, governance_path = load_doc(repo_root, Path(args.governance), "PowerShell finding governance")
    except GovernanceError as exc:
        errors.append(str(exc))
        governance_path = str(args.governance)
    try:
        assembly_report, assembly_path = load_optional_doc(
            repo_root,
            Path(args.assembly_parity_report),
            "PowerShell assembly parity report",
            warnings,
        )
    except GovernanceError as exc:
        errors.append(str(exc))
        assembly_path = str(args.assembly_parity_report)
    if assembly_report is not None:
        assembly_errors = validate_assembly_parity_report(repo_root, assembly_path, assembly_report)
        errors.extend(assembly_errors)
        if not assembly_errors:
            assembly_report_for_coverage = assembly_report
    if governance:
        errors.extend(validate_governance_doc(repo_root, governance, assembly_report_for_coverage, today))
    required_reports = [Path(path) for path in (args.finding_report or [])]
    if not required_reports:
        required_reports = [DEFAULT_CUSTOM_REPORT, DEFAULT_RULE_RISK_REPORT]
    if not getattr(args, "allow_missing_analyzer_report", False) and DEFAULT_ANALYZER_REPORT not in required_reports:
        required_reports.append(DEFAULT_ANALYZER_REPORT)
    optional_reports = [Path(path) for path in (args.optional_finding_report or [])]
    if getattr(args, "allow_missing_analyzer_report", False):
        analyzer_path = DEFAULT_ANALYZER_REPORT.as_posix()
        optional_report_paths = {path.as_posix() for path in optional_reports}
        required_report_paths = {path.as_posix() for path in required_reports}
        if analyzer_path not in optional_report_paths and analyzer_path not in required_report_paths:
            optional_reports.append(DEFAULT_ANALYZER_REPORT)
    required_report_paths = {path.as_posix() for path in required_reports}
    optional_reports = [path for path in optional_reports if path.as_posix() not in required_report_paths]
    findings, input_reports = collect_findings(repo_root, required_reports, optional_reports, errors, warnings)
    classifications, delta, classification_errors = classify_findings(governance, findings, today) if governance else ([], {}, [])
    errors.extend(classification_errors)
    assembly_success: bool | None = None
    if isinstance(assembly_report, dict):
        assembly_success = report_validation_success_state(assembly_report)[0]
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_NUMBER,
        "parent_issue": 260,
        "depends_on": [262, 263, 264, 265],
        "governance": {
            "path": governance_path,
            "schema_version": governance.get("schema_version") if governance else None,
            "policy": governance.get("policy", {}) if governance else {},
            "classification_rule_count": len(governance.get("classification_rules", [])) if governance else 0,
        },
        "assembly_parity_report": {
            "path": assembly_path,
            "present": assembly_report is not None,
            "schema_version": assembly_report.get("schema_version") if isinstance(assembly_report, dict) else None,
            "validation_success": assembly_success,
            "generated_output_paths": sorted(generated_output_paths(assembly_report_for_coverage)),
        },
        "input_reports": input_reports,
        "summary": {},
        "baseline_delta": delta
        or {
            "baseline_record_count": 0,
            "matched_baseline_record_count": 0,
            "suppression_count": 0,
            "matched_suppression_count": 0,
            "unclassified_finding_count": 0,
            "decision_counts": {},
            "baseline_match_counts": {},
            "suppression_match_counts": {},
            "as_of": today.isoformat(),
        },
        "classifications": classifications,
        "controlled_fail_closed_proof": governance.get("control_proofs", []) if governance else [],
        "validation": {
            "success": not errors,
            "errors": errors,
            "warnings": warnings,
        },
    }
    report["summary"] = governance_summary(findings, classifications, report["baseline_delta"])
    return report, errors, warnings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--governance", default=DEFAULT_GOVERNANCE.as_posix(), help="Governance JSON policy")
    parser.add_argument(
        "--finding-report",
        action="append",
        default=[],
        help="Required analyzer/custom finding report JSON. Defaults to #263/#264 reports.",
    )
    parser.add_argument(
        "--optional-finding-report",
        action="append",
        default=[],
        help="Optional finding report JSON. Missing optional reports are warnings.",
    )
    parser.add_argument(
        "--assembly-parity-report",
        default=DEFAULT_ASSEMBLY_PARITY_REPORT.as_posix(),
        help="#265 assembly parity report JSON.",
    )
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix(), help="Output JSON report path")
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix(), help="Output Markdown report path")
    parser.add_argument("--as-of-date", default="", help="ISO date for stale baseline checks")
    parser.add_argument(
        "--allow-missing-analyzer-report",
        action="store_true",
        help="Explicitly permit a missing #262 analyzer report as optional local evidence.",
    )
    parser.add_argument("--no-write", action="store_true", help="Build the report without writing output files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    report, _errors, _warnings = build_report(args)
    repo_root = Path(args.repo_root).resolve()
    if not args.no_write:
        try:
            write_outputs(repo_root, report, Path(args.json_output), Path(args.markdown_output))
        except GovernanceError as exc:
            mark_report_write_failure(report, str(exc))
    if report["validation"]["success"]:
        return 0
    for error in report["validation"]["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1
